# Copyright (C) 2009,2010 Canonical
#
# Authors:
#  Michael Vogt, Matthew McGowan
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import copy
from gi.repository import GObject
from gi.repository import Gtk, GdkPixbuf
import logging
import os
import xapian
import threading
import time

from gettext import gettext as _

from softwarecenter.enums import (Icons, SortMethods,
                                  XapianValues, NonAppVisibility,
                                  DEFAULT_SEARCH_LIMIT)

from softwarecenter.utils import ExecutionTime, SimpleFileDownloader
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.database import Application, SearchQuery, LocaleSorter, TopRatedSorter
from softwarecenter.distro import get_distro
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR


# global cache icons to speed up rendering
_app_icon_cache = {}


LOG = logging.getLogger(__name__)


class AppEnquire(object):
    """
    A interface to enquire data from a xapian database. 
    It can combined with any xapian querry and with
    a generic filter function (that can filter on data not
    available in xapian)
    """

    def __init__(self, cache, db):
        """
        Init a AppEnquire object

        :Parameters:
        - `cache`: apt cache (for stuff like the overlay icon)
        - `db`: a xapian.Database that contians the applications
        """

        self.cache = cache
        self.db = db
        self.distro = get_distro()
        self.search_query = SearchQuery(None)
        self.nonblocking_load = True
        self.sortmode = SortMethods.UNSORTED
        self.nonapps_visible = NonAppVisibility.MAYBE_VISIBLE
        self.limit = DEFAULT_SEARCH_LIMIT
        self.filter = None
        self.exact = False
        self.nr_pkgs = 0
        self.nr_apps = 0
        self._matches = []
        self.match_docids = set()

        # support for callbacks when a search is complete
        self.on_query_complete = None
        self.callback_user_data = None

    def __len__(self):
        return len(self._matches)

    @property
    def matches(self):
        """ return the list of matches as xapian.MSetItem """
        return self._matches

    def _threaded_perform_search(self):
        self._perform_search_complete = False
        thread_name = 'ThreadedQuery-%s' % (threading.active_count()+1)
        t = threading.Thread(
            target=self._blocking_perform_search, name=thread_name)
        t.start()
        # don't block the UI while the thread is running
        while not self._perform_search_complete:
            time.sleep(0.02) # 50 fps
            while Gtk.events_pending():
                Gtk.main_iteration()

        # call the query-complete callback
        if self.on_query_complete:
            self.on_query_complete(self, *self.callback_user_data)

    def _get_estimate_nr_apps_and_nr_pkgs(self, enquire, q, xfilter):
        # filter out docs of pkgs of which there exists a doc of the app
        enquire.set_query(xapian.Query(xapian.Query.OP_AND, 
                                       q, xapian.Query("ATapplication")))

        try:
            tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        except Exception, e:
            print e
            return (0, 0)

        nr_apps = tmp_matches.get_matches_estimated()
        enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                       q, xapian.Query("XD")))
        tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        nr_pkgs = tmp_matches.get_matches_estimated() - nr_apps
        return (nr_apps, nr_pkgs)

    def _blocking_perform_search(self):
        # WARNING this call may run in a thread, so its *not* 
        #         allowed to touch gtk, otherwise hell breaks loose

        # performance only: this is only needed to avoid the 
        # python __call__ overhead for each item if we can avoid it

        # use a unique instance of both enquire and xapian database
        # so concurrent queries dont result in an inconsistent database

        # an alternative would be to serialise queries
        enquire = xapian.Enquire(self.db.xapiandb)

        if self.filter and self.filter.required:
            xfilter = self.filter
        else:
            xfilter = None
        # go over the queries
        self.nr_apps, self.nr_pkgs = 0, 0
        _matches = self._matches
        match_docids = self.match_docids

        for q in self.search_query:
            LOG.debug("initial query: '%s'" % q)

            # for searches we may want to disable show/hide
            terms = [term for term in q]
            exact_pkgname_query = (len(terms) == 1 and 
                                   terms[0].startswith("XP"))

            with ExecutionTime("calculate nr_apps and nr_pkgs: "):
                nr_apps, nr_pkgs = self._get_estimate_nr_apps_and_nr_pkgs(enquire, q, xfilter)
                self.nr_apps += nr_apps
                self.nr_pkgs += nr_pkgs

            # only show apps by default (unless in always visible mode)
            if self.nonapps_visible != NonAppVisibility.ALWAYS_VISIBLE:
                if not exact_pkgname_query:
                    q = xapian.Query(xapian.Query.OP_AND, 
                                     xapian.Query("ATapplication"),
                                     q)

            LOG.debug("nearly completely filtered query: '%s'" % q)

            # filter out docs of pkgs of which there exists a doc of the app
            # FIXME: make this configurable again?
            enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                           q, xapian.Query("XD")))

            # sort results

            # cataloged time - what's new category
            if self.sortmode == SortMethods.BY_CATALOGED_TIME:
                if (self.db._axi_values and 
                    "catalogedtime" in self.db._axi_values):
                    enquire.set_SortMethods.by_value(
                        self.db._axi_values["catalogedtime"], reverse=True)
                else:
                    logging.warning("no catelogedtime in axi")
            elif self.sortmode == SortMethods.BY_TOP_RATED:
                review_loader = get_review_loader(self.cache)
                sorter = TopRatedSorter(self.db, review_loader)
                enquire.set_sort_by_key(sorter, reverse=True)
            # search ranking - when searching
            elif self.sortmode == SortMethods.BY_SEARCH_RANKING:
                #enquire.set_SortMethods.by_value(XapianValues.POPCON)
                # use the default enquire.set_SortMethods.by_relevance()
                pass
            # display name - all categories / channels
            elif (self.db._axi_values and 
                  "display_name" in self.db._axi_values):
                enquire.set_sort_by_key(LocaleSorter(self.db), reverse=False)
                # fallback to pkgname - if needed?
            # fallback to pkgname - if needed?
            else:
                enquire.set_SortMethods.by_value_then_relevance(
                    XapianValues.PKGNAME, False)
                    
            # set limit
            #~ try:
            if self.limit == 0:
                matches = enquire.get_mset(0, len(self.db))#, None, xfilter)
            else:
                matches = enquire.get_mset(0, self.limit)#, None, xfilter)
            LOG.debug("found ~%i matches" % matches.get_matches_estimated())
            #~ except:
                #~ logging.exception("get_mset")
                #~ matches = []
                
            # promote exact matches to a "app", this will make the 
            # show/hide technical items work correctly
            if exact_pkgname_query and len(matches) == 1:
                self.nr_apps += 1
                self.nr_pkgs -= 2

            # add matches, but don't duplicate docids
            with ExecutionTime("append new matches to existing ones:"):
                for match in matches:
                    if not match.docid in match_docids:
                        _matches.append(match)
                        match_docids.add(match.docid)

        # if we have no results, try forcing pkgs to be displayed
        # if not NonAppVisibility.NEVER_VISIBLE is set
        if (not _matches and
            self.nonapps_visible not in (NonAppVisibility.ALWAYS_VISIBLE,
                                         NonAppVisibility.NEVER_VISIBLE)):
            self.nonapps_visible = NonAppVisibility.ALWAYS_VISIBLE
            self._blocking_perform_search()

        # wake up the UI if run in a search thread
        self._perform_search_complete = True
        return

    def set_query_complete_callback(self, cb, *user_data):
        self.on_query_complete = cb
        self.callback_user_data = user_data
        return

    def set_query(
            self,  search_query, 
            limit=DEFAULT_SEARCH_LIMIT,
            sortmode=SortMethods.UNSORTED, 
            filter=None,
            exact=False,
            nonapps_visible=NonAppVisibility.MAYBE_VISIBLE,
            nonblocking_load=True,
            persistent_duplicate_filter=False):

        """
        Set a new query

        :Parameters:
        - `search_query`: a single search as a xapian.Query or a list
        - `limit`: how many items the search should return (0 == unlimited)
        - `sortmode`: sort the result
        - `filter`: filter functions that can be used to filter the
                    data further. A python function that gets a pkgname
        - `exact`: If true, indexes of queries without matches will be
                    maintained in the store (useful to show e.g. a row
                    with "??? not found")
        - `nonapps_visible`: decide whether adding non apps in the model or not.
                             Can be NonAppVisibility.ALWAYS_VISIBLE/NonAppVisibility.MAYBE_VISIBLE
                             /NonAppVisibility.NEVER_VISIBLE
                             (NonAppVisibility.MAYBE_VISIBLE will return non apps result
                              if no matching apps is found)
        - `nonblocking_load`: set to False to execute the query inside the current
                              thread.  Defaults to True to allow the search to be
                              performed without blocking the UI.
        - 'persistent_duplicate_filter': if True allows filtering of duplicate
                                         matches across multiple queries
        """

        self.search_query = SearchQuery(search_query)
        self.limit = limit
        self.sortmode = sortmode
        # we need a copy of the filter here because otherwise comparing
        # two models will not work
        self.filter = copy.copy(filter)
        self.exact = exact
        self.nonblocking_load = nonblocking_load
        self.nonapps_visible = nonapps_visible

        # no search query means "all"
        if not search_query:
            self.search_query = SearchQuery(xapian.Query(""))
            self.sortmode = SortMethods.BY_ALPHABET
            self.limit = 0

        # flush old query matches
        self._matches = []
        if not persistent_duplicate_filter:
            self.match_docids = set()

        # we support single and list search_queries,
        # if list we append them one by one
        with ExecutionTime("populate model from query: '%s' (threaded: %s)" % (
                " ; ".join([str(q) for q in self.search_query]),
                self.nonblocking_load)):
            if self.nonblocking_load:
                self._threaded_perform_search()
            else:
                self._blocking_perform_search()
        return True

#    def get_pkgnames(self):
#        xdb = self.db.xapiandb
#        pkgnames = []
#        for m in self.matches:
#            doc = xdb.get_document(m.docid)
#            pkgnames.append(doc.get_value(XapianValues.PKGNAME) or doc.get_data())
#        return pkgnames

#    def get_applications(self):
#        apps = []
#        for pkgname in self.get_pkgnames():
#            apps.append(Application(pkgname=pkgname))
#        return apps

    def get_docids(self):
        """ get the docids of the current matches """
        xdb = self.db.xapiandb
        return [xdb.get_document(m.docid).get_docid() for m in self._matches]

    def get_documents(self):
        """ get the xapian.Document objects of the current matches """
        xdb = self.db.xapiandb
        return [xdb.get_document(m.docid) for m in self._matches]


class CategoryRowReference:
    """ A simple container for Category properties to be 
        displayed in a AppListStore or AppTreeStore
    """

    def __init__(self, untranslated_name, display_name, subcats, pkg_count):
        self.untranslated_name = untranslated_name
        self.display_name = GObject.markup_escape_text(display_name)
        #self.subcategories = subcats
        self.pkg_count = pkg_count
        self.vis_count = pkg_count
        return


class UncategorisedRowRef(CategoryRowReference):

    def __init__(self, pkg_count, display_name=None):
        if display_name is None:
            display_name = _("Uncategorized")

        CategoryRowReference.__init__(self,
                                      "uncategorized",
                                      display_name,
                                      None, pkg_count)
        return


class _AppPropertiesHelper(object):
    """ Baseclass that contains common functions for our
        liststore/treestore, only useful for subclassing
    """

    def _download_icon_and_show_when_ready(self, cache, pkgname, icon_file_name):
        LOG.debug("did not find the icon locally, must download %s" % icon_file_name)

        def on_image_download_complete(downloader, image_file_path):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_file_path,
                                                      self.icon_size,
                                                      self.icon_size)
            # replace the icon in the icon_cache now that we've got the real one
            icon_file = os.path.splitext(os.path.basename(image_file_path))[0]
            self.icon_cache[icon_file] = pb
        
        url = get_distro().get_downloadable_icon_url(cache, pkgname, icon_file_name)
        if url is not None:
            icon_file_path = os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR, icon_file_name)
            image_downloader = SimpleFileDownloader()
            image_downloader.connect('file-download-complete', on_image_download_complete)
            image_downloader.download_file(url, icon_file_path)

    def update_availability(self, doc):
        doc.available = None
        doc.installed = None
        self.is_installed(doc)
        return

    def is_available(self, doc):
        if doc.available is None:
            pkgname = self.get_pkgname(doc)
            doc.available = pkgname in self.cache
        return doc.available

    def is_installed(self, doc):
        if doc.installed is None:
            pkgname = self.get_pkgname(doc)
            if doc.available is None:
                doc.available = pkgname in self.cache
            doc.installed = doc.available and self.cache[pkgname].is_installed
        return doc.installed

    def get_pkgname(self, doc):
        return self.db.get_pkgname(doc)

    def get_application(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)
        pkgname = self.db.get_pkgname(doc)
        # TODO: requests
        return Application(appname, pkgname, "")

    def get_appname(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)
        if not appname:
            appname = self.db.get_summary(doc)
            summary = self.get_pkgname(doc)
        else:
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, self.get_pkgname(doc))
        return appname

    def get_markup(self, doc):
        appname = doc.get_value(XapianValues.APPNAME)

        if not appname:
            appname = self.db.get_summary(doc)
            summary = self.get_pkgname(doc)
        else:
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, self.get_pkgname(doc))

            summary = self.db.get_summary(doc)

        return "%s\n<small>%s</small>" % (
                 GObject.markup_escape_text(appname),
                 GObject.markup_escape_text(summary))

    def get_icon(self, doc):
        try:
            icon_file_name = self.db.get_iconname(doc)
            if icon_file_name:
                icon_name = os.path.splitext(icon_file_name)[0]
                if icon_name in self.icon_cache:
                    return self.icon_cache[icon_name]
                # icons.load_icon takes between 0.001 to 0.01s on my
                # machine, this is a significant burden because get_value
                # is called *a lot*. caching is the only option
                
                # look for the icon on the iconpath
                if self.icons.has_icon(icon_name):
                    icon = self.icons.load_icon(icon_name, self.icon_size, 0)
                    if icon:
                        self.icon_cache[icon_name] = icon
                        return icon
                #~ elif self.db.get_icon_needs_download(doc):
                    #~ self._download_icon_and_show_when_ready(
                        #~ self.cache, 
                        #~ self.get_pkgname(doc),
                        #~ icon_file_name)
                    #~ # display the missing icon while the real one downloads
                    #~ self.icon_cache[icon_name] = self._missing_icon
        except GObject.GError, e:
            LOG.debug("get_icon returned '%s'" % e)
        return self._missing_icon

    def get_review_stats(self, doc):
        return self.review_loader.get_review_stats(self.get_application(doc))

    def get_transaction_progress(self, doc):
        pkgname = self.get_pkgname(doc)
        if pkgname in self.backend.pending_transactions:
            return self.backend.pending_transactions[pkgname].progress
        return -1


class AppPropertiesHelper(_AppPropertiesHelper):

    def __init__(self, db, cache, icons, icon_size=48, global_icon_cache=False):
        self.db = db
        self.cache = cache

        # reviews stats loader
        self.review_loader = get_review_loader(cache)

        # icon jazz
        self.icons = icons
        self.icon_size = icon_size
        # cache the 'missing icon' used in the treeview for apps without an icon
        self._missing_icon = icons.load_icon(Icons.MISSING_APP,
                                             icon_size, 0)

        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}
        return

    def get_icon_at_size(self, doc, width, height):
        pixbuf = self.get_icon(doc)
        pixbuf = pixbuf.scale_simple(width, height,
                                     GdkPixbuf.InterpType.BILINEAR)
        return pixbuf

    def get_transaction_progress(self, doc):
        raise NotImplemented


class AppGenericStore(_AppPropertiesHelper):

    # column types
    COL_TYPES = (GObject.TYPE_PYOBJECT,)

    # column id
    COL_ROW_DATA = 0

    # default icon size displayed in the treeview
    ICON_SIZE = 32

    def __init__(self, db, cache, icons, icon_size, global_icon_cache):
        # the usual suspects
        self.db = db
        self.cache = cache

        # reviews stats loader
        self.review_loader = get_review_loader(cache)

        # backend stuff
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)

        # keep track of paths for transactions in progress
        self.transaction_path_map = {}

        # icon jazz
        self.icons = icons
        self.icon_size = icon_size

        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}

        # active row path
        self.active_row = None

        # cache the 'missing icon' used in the treeview for apps without an icon
        self._missing_icon = icons.load_icon(Icons.MISSING_APP, icon_size, 0)

        self._in_progress = False
        self._break = False

        # other stuff
        self.active = False
        return

    # FIXME: port from 
    @property
    def installable_apps(self):
        return []
    @property
    def existing_apps(self):
        return []

    def notify_action_request(self, doc, path):
        pkgname = str(self.get_pkgname(doc))
        self.transaction_path_map[pkgname] = (path, self.get_iter(path))
        return

    # the following methods ensure that the contents data is refreshed
    # whenever a transaction potentially changes it: 
    def _on_transaction_started(self, backend, pkgname, appname, trans_id, trans_type):
        #~ self._refresh_transaction_map()
        pass

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if pkgname in self.transaction_path_map:
            path, it = self.transaction_path_map[pkgname]
            self.row_changed(path, it)
        return

    def _on_transaction_finished(self, backend, result):
        pkgname = str(result.pkgname)
        if pkgname in self.transaction_path_map:
            path, it = self.transaction_path_map[pkgname]
            doc = self.get_value(it, self.COL_ROW_DATA)
            self.update_availability(doc)
            self.row_changed(path, it)
            del self.transaction_path_map[pkgname]


class AppListStore(Gtk.ListStore, AppGenericStore):
    """ use for flat applist views. for large lists this appends rows approx
        three times faster than the AppTreeStore equivalent
    """

    LOAD_INITIAL   = 75

    def __init__(self, db, cache, icons, icon_size=AppGenericStore.ICON_SIZE, 
                 global_icon_cache=True):
        AppGenericStore.__init__(
            self, db, cache, icons, icon_size, global_icon_cache)
        Gtk.ListStore.__init__(self)
        self.set_column_types(self.COL_TYPES)

        self.current_matches = None
        return

    def set_from_matches(self, matches):
        """ set the content of the liststore based on a list of
            xapian.MSetItems
        """

        self.current_matches = matches
        n_matches = len(matches)
        if n_matches == 0: return
    
        db = self.db.xapiandb
        extent = min(self.LOAD_INITIAL, n_matches-1)

        with ExecutionTime("store.append_initial"):
            for doc in [db.get_document(m.docid) for m in matches][:extent]:
                doc.available = doc.installed = None
                self.append((doc,))

        if n_matches == extent: return

        with ExecutionTime("store.append_placeholders"):
            for i in range(n_matches - extent):
                self.append()

        self.buffer_icons()
        return

    def load_range(self, indices, step):
        db = self.db.xapiandb
        matches = self.current_matches

        n_matches = len(matches)

        start = indices[0]
        end = start + step

        if end >= n_matches:
            end = n_matches

        for i in range(start, end):
            if self[(i,)][0]: continue
            doc = db.get_document(matches[i].docid)
            doc.available = doc.installed = None
            self[(i,)][0] = doc
        return

    def clear(self):
        # reset the tranaction map because it will now be invalid
        self.transaction_path_map = {}
        self.current_matches = None
        Gtk.ListStore.clear(self)
        return

    def buffer_icons(self):
        def buffer_icons():
            #~ print "Buffering icons ..."
            t0 = GObject.get_current_time()
            db = self.db.xapiandb
            for m in self.current_matches:
                doc = db.get_document(m.docid)

                # calling get_icon is enough to cache the icon
                self.get_icon(doc)

                while Gtk.events_pending():
                    Gtk.main_iteration()

            #~ import sys
            #~ t_lapsed = round(GObject.get_current_time() - t0, 3)
            #~ print "Appstore buffered icons in %s seconds" % t_lapsed
            #from softwarecenter.utils import get_nice_size
            #~ cache_size = get_nice_size(sys.getsizeof(_app_icon_cache))
            #~ print "Number of icons in cache: %s consuming: %sb" % (len(_app_icon_cache), cache_size)
            return False    # remove from sources on completion

        GObject.idle_add(buffer_icons)
        return


class AppTreeStore(Gtk.TreeStore, AppGenericStore):
    """ A treestore based application model
    """

    def __init__(self, db, cache, icons, icon_size=AppGenericStore.ICON_SIZE, 
                 global_icon_cache=True):
        AppGenericStore.__init__(
            self, db, cache, icons, icon_size, global_icon_cache)
        Gtk.TreeStore.__init__(self)
        self.set_column_types(self.COL_TYPES)
        return

    def set_documents(self, parent, documents):
        for doc in documents:
            doc.available = None; doc.installed = None
            self.append(parent, (doc,))

        self.transaction_path_map = {}
        return

    def set_category_documents(self, cat, documents):
        category = CategoryRowReference(cat.untranslated_name,
                                        cat.name,
                                        cat.subcategories,
                                        len(documents))

        it = self.append(None, (category,))
        self.set_documents(it, documents)
        return it

    def set_nocategory_documents(self, documents, display_name=None):
        category = UncategorisedRowRef(len(documents), display_name)
        it = self.append(None, (category,))
        self.set_documents(it, documents)
        return it

    def clear(self):
        # reset the tranaction map because it will now be invalid
        self.transaction_path_map = {}
        Gtk.TreeStore.clear(self)
        return
