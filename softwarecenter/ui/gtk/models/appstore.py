# Copyright (C) 2009,2010 Canonical
#
# Authors:
#  Michael Vogt
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
import glib
import gobject
import gtk
import logging
import math
import os
import xapian
import time
import threading

from softwarecenter.enums import (
    DEFAULT_SEARCH_LIMIT,
    MISSING_APP_ICON,
    SORT_UNSORTED,
    SORT_BY_ALPHABET,
    SORT_BY_CATALOGED_TIME,
    SORT_BY_SEARCH_RANKING,
    XAPIAN_VALUE_PKGNAME,
    XAPIAN_VALUE_APPNAME,
    )
from softwarecenter.utils import ExecutionTime, SimpleFileDownloader
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.database import Application, SearchQuery, LocaleSorter

from softwarecenter.distro import get_distro
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR

from gettext import gettext as _

# global cache icons to speed up rendering
_app_icon_cache = {}

LOG = logging.getLogger(__name__)

class AppStore(gtk.GenericTreeModel):
    """
    A subclass GenericTreeModel that reads its data from a xapian
    database. It can combined with any xapian querry and with
    a generic filter function (that can filter on data not
    available in xapian)
    """

    (COL_APP_NAME,
     COL_TEXT,
     COL_MARKUP,
     COL_ICON,
     COL_INSTALLED,
     COL_AVAILABLE,
     COL_PKGNAME,
     COL_RATING,
     COL_NR_REVIEWS,
     COL_IS_ACTIVE,
     COL_ACTION_IN_PROGRESS,
     COL_EXISTS,
     COL_ACCESSIBLE,
     COL_REQUEST) = range(14)

    column_type = (str,
                   str,
                   str,
                   gtk.gdk.Pixbuf,
                   bool,
                   bool,
                   str,
                   float,
                   int,
                   bool,
                   int,
                   bool,
                   str,
                   str)

    ICON_SIZE = 24
    MAX_STARS = 5

    (NONAPPS_ALWAYS_VISIBLE,
     NONAPPS_MAYBE_VISIBLE,
     NONAPPS_NEVER_VISIBLE) = range (3)

    def __init__(self, cache, db, icons, search_query=None, 
                 limit=DEFAULT_SEARCH_LIMIT,
                 sortmode=SORT_UNSORTED, filter=None,
                 icon_size=ICON_SIZE, global_icon_cache=True, 
                 nonapps_visible=NONAPPS_MAYBE_VISIBLE,
                 nonblocking_load=True, search_term=None):
        """
        Initalize a AppStore.

        :Parameters:
        - `cache`: apt cache (for stuff like the overlay icon)
        - `db`: a xapian.Database that contians the applications
        - `icons`: a gtk.IconTheme that contains the icons
        - `search_query`: a single search as a xapian.Query or a list
        - `limit`: how many items the search should return (0 == unlimited)
        - `sortmode`: sort the result
        - `filter`: filter functions that can be used to filter the
                    data further. A python function that gets a pkgname
        - `nonapps_visible`: decide whether adding non apps in the model or not.
                             Can be NONAPPS_ALWAYS_VISIBLE/NONAPPS_MAYBE_VISIBLE
                             /NONAPPS_NEVER_VISIBLE
                             (NONAPPS_MAYBE_VISIBLE will return non apps result
                              if no matching apps is found)
        - `nonblocking_load`: set to False to execute the query inside the current
                              thread.  Defaults to True to allow the search to be
                              performed without blocking the UI. 
        - `search_term`: a string containing the search_term. Atm we only use
                         this for custom package lists. 
        """
        gtk.GenericTreeModel.__init__(self)
        self.search_query = SearchQuery(search_query)
        self.cache = cache
        self.db = db
        self.db.connect("reopen", self._on_db_reopen)
        self.distro = get_distro()
        self.icons = icons
        self.icon_size = icon_size
        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}
        self.nonblocking_load = nonblocking_load

        # invalidate the cache on icon theme changes
        self.icons.connect("changed", self._clear_app_icon_cache)
        self._appicon_missing_icon = self.icons.load_icon(MISSING_APP_ICON, self.icon_size, 0)
        self.sortmode = sortmode
        # we need a copy of the filter here because otherwise comparing
        # two models will not work
        self.filter = copy.copy(filter)
        self.active = True
        # These track if technical (non-applications) are being displayed
        # and if the user explicitly requested they be.
        self.nonapps_visible = nonapps_visible
        self._explicit_nonapp_visibility = False
        # new goodness
        self.nr_pkgs = 0
        self.nr_apps = 0
        # reviews
        self.review_loader = get_review_loader(self.cache)
        # backend stuff
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        # rowref of the active app and last active app
        self.active_app = None
        self._prev_active_app = 0
        self.limit = limit
        # keep track of indicies for transactions in progress
        self.transaction_index_map = {}
        # no search query means "all"
        if not search_query:
            self.search_query = SearchQuery(xapian.Query(""))
            self.sortmode = SORT_BY_ALPHABET
            self.limit = 0
        # custom package lists
        self.search_term = search_term
        self.apps = []
        self._perform_search()

    def _perform_search(self):
        # we support single and list search_queries,
        # if list we append them one by one
        with ExecutionTime("populate model from query: '%s' (threaded: %s)" % (
                " ; ".join([str(q) for q in self.search_query]),
                self.nonblocking_load)):
            if self.nonblocking_load:
                self._threaded_perform_search()
            else:
                self._blocking_perform_search()

    def _on_db_reopen(self, db):
        logging.debug("got db-reopen signal, refreshing search docids")
        self._perform_search()

    def _threaded_perform_search(self):
        self._perform_search_complete = False
        t = threading.Thread(target=self._blocking_perform_search)
        t.start()
        # don't block the UI while the thread is running
        while not self._perform_search_complete:
            time.sleep(0.02) # 50 fps
            while gtk.events_pending():
                gtk.main_iteration()

    def _get_estimate_nr_apps_and_nr_pkgs(self, enquire, q, xfilter):
        # filter out docs of pkgs of which there exists a doc of the app
        enquire.set_query(xapian.Query(xapian.Query.OP_AND, 
                                       q, xapian.Query("ATapplication")))
        tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        nr_apps = tmp_matches.get_matches_estimated()
        enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                       q, xapian.Query("XD")))
        tmp_matches = enquire.get_mset(0, len(self.db), None, xfilter)
        nr_pkgs = tmp_matches.get_matches_estimated() - nr_apps
        return (nr_apps, nr_pkgs)

    def _blocking_perform_search(self):
        # WARNING this call may run in a thread, so its *not* 
        #         allowed to touch gtk, otherwise hell breaks loose

        # custom package lists
        if self.search_term and ',' in self.search_term:
            self.apps = []
            terms = []
            for term in self.search_term.split(','):
                term = term.strip()
                if term and not term in terms:
                    terms.append(term)
                    app = Application('', term.split('?')[0])
                    if '?' in term:
                        app.request = term.split('?')[1]
                    self.apps.append(app)
            self.matches = self.db.get_exact_matches(terms)
            self._perform_search_complete = True
            return

        # performance only: this is only needed to avoid the 
        # python __call__ overhead for each item if we can avoid it
        if self.filter and self.filter.required:
            xfilter = self.filter
        else:
            xfilter = None
        # go over the queries
        self.nr_apps, self.nr_pkgs = 0, 0
        self.matches = []
        self.match_docids = set()
        
        # acquire lock before performing the search or block until the
        # lock becomes available
        self.db.acquire_search_lock()

        # now do the search
        for q in self.search_query:
            enquire = xapian.Enquire(self.db.xapiandb)
            LOG.debug("initial query: '%s'" % q)

            # for searches we may want to disable show/hide
            terms = [term for term in q]
            exact_pkgname_query = (len(terms) == 1 and terms[0].startswith("XP"))

            with ExecutionTime("calculate nr_apps and nr_pkgs: "):
                nr_apps, nr_pkgs = self._get_estimate_nr_apps_and_nr_pkgs(enquire, q, xfilter)
                self.nr_apps += nr_apps
                self.nr_pkgs += nr_pkgs

            # only show apps by default (unless we 
            if self.nonapps_visible != self.NONAPPS_ALWAYS_VISIBLE:
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
            if self.sortmode == SORT_BY_CATALOGED_TIME:
                if (self.db._axi_values and 
                    "catalogedtime" in self.db._axi_values):
                    enquire.set_sort_by_value(
                        self.db._axi_values["catalogedtime"], reverse=True)
                else:
                    logging.warning("no catelogedtime in axi")

            # search ranking - when searching
            elif self.sortmode == SORT_BY_SEARCH_RANKING:
                #enquire.set_sort_by_value(XAPIAN_VALUE_POPCON)
                # use the default enquire.set_sort_by_relevance()
                pass
            # display name - all categories / channels
            elif (self.db._axi_values and 
                  "display_name" in self.db._axi_values):
                enquire.set_sort_by_key(LocaleSorter(self.db), reverse=False)
                # fallback to pkgname - if needed?
            # fallback to pkgname - if needed?
            else:
                enquire.set_sort_by_value_then_relevance(
                    XAPIAN_VALUE_PKGNAME, False)
                    
            # set limit
            try:
                if self.limit == 0:
                    matches = enquire.get_mset(0, len(self.db), None, xfilter)
                else:
                    matches = enquire.get_mset(0, self.limit, None, xfilter)
                LOG.debug("found ~%i matches" % matches.get_matches_estimated())
            except:
                logging.exception("get_mset")
                matches = []
                
            # promote exact matches to a "app", this will make the 
            # show/hide technical items work correctly
            if exact_pkgname_query and len(matches) == 1:
                self.nr_apps += 1
                self.nr_pkgs -= 2

            # add matches, but don't duplicate docids
            with ExecutionTime("append new matches to existing ones:"):
                for match in matches:
                    if not match.docid in self.match_docids:
                        self.matches.append(match)
                        self.match_docids.add(match.docid)

        # release the lock here because the following check may trigger
        # calling this function again (and we would deadlock otherwise)
        self.db.release_search_lock()

        # if we have no results, try forcing pkgs to be displayed
        # if not NONAPPS_NEVER_VISIBLE is set
        if (not self.matches and
            self.nonapps_visible not in (self.NONAPPS_ALWAYS_VISIBLE,
                                         self.NONAPPS_NEVER_VISIBLE)):
            self.nonapps_visible = self.NONAPPS_ALWAYS_VISIBLE
            self._blocking_perform_search()
            
        # wake up the UI if run in a search thread
        self._perform_search_complete = True
        return

    def _clear_app_icon_cache(self, theme):
        self.icon_cache.clear()

    # internal helper
    def _set_active_app(self, path):
        """ helper that emits row_changed signals for the new
            and previous selected app
        """
        self.active_app = path
        self.row_changed(self._prev_active_app,
                         self.get_iter(self._prev_active_app))
        self._prev_active_app = path
        self.row_changed(path, self.get_iter(path))

    def _calc_normalized_rating(self, raw_rating):
        if raw_rating:
            return int(self.MAX_STARS * math.log(raw_rating)/math.log(self.db.popcon_max+1))
        return 0

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if pkgname in self.transaction_index_map:
            row = self[self.transaction_index_map[pkgname]]
            self.row_changed(row.path, row.iter)
            
    # the following methods ensure that the contents data is refreshed
    # whenever a transaction potentially changes it: see _refresh_contents.

    def _on_transaction_started(self, backend, pkgname, appname, trans_id, trans_type):
        self._register_transaction_index_for_pkgname(pkgname)

    def _register_transaction_index_for_pkgname(self, pkgname_to_match):
        for index in range(len(self.matches)):
            doc = self.matches[index].document
            try:
                pkgname = self.db.get_pkgname(doc)
            except: # 'not found' Application items for custom package lists
                pkgname = doc.pkgname
            if pkgname == pkgname_to_match:
                self.transaction_index_map[pkgname] = index
                return
            # process one event 
            gtk.main_iteration(block=False)
                
    def _on_transaction_finished(self, backend, result):
        if result.pkgname in self.transaction_index_map:
            del self.transaction_index_map[result.pkgname]

    def _download_icon_and_show_when_ready(self, cache, pkgname, icon_file_name):
        LOG.debug("did not find the icon locally, must download %s" % icon_file_name)
        def on_image_download_complete(downloader, image_file_path):
            pb = gtk.gdk.pixbuf_new_from_file_at_size(icon_file_path,
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

    # GtkTreeModel functions
    def on_get_flags(self):
        return (gtk.TREE_MODEL_LIST_ONLY|
                gtk.TREE_MODEL_ITERS_PERSIST)
    def on_get_n_columns(self):
        return len(self.column_type)
    def on_get_column_type(self, index):
        return self.column_type[index]
    def on_get_iter(self, path):
        #LOG.debug("on_get_iter: %s" % path)
        if len(self.matches) == 0:
            return None
        index = path[0]
        return index
    def on_get_path(self, rowref):
        LOG.debug("on_get_path: %s" % rowref)
        return rowref
    def on_get_value(self, rowref, column):
        #LOG.debug("on_get_value: %s %s" % (rowref, column))
        doc = self.matches[rowref].document

        # 'not found' applications for custom package lists
        if type(doc) == Application:
            app = doc
            if column == self.COL_APP_NAME:
                if app.request:
                    return app.name
                return _("Not found")
            elif column == self.COL_TEXT:
                return "%s\n" % app.pkgname
            elif column == self.COL_MARKUP:
                if app.request:
                    s = "%s\n<small>%s</small>" % (
                        gobject.markup_escape_text(app.name),
                        gobject.markup_escape_text(_("Not found")))
                    return s
                s = "<span foreground='#666'>%s\n<small>%s</small></span>" % (
                    gobject.markup_escape_text(_("Not found")),
                    gobject.markup_escape_text(app.pkgname))
                return s
            elif column == self.COL_ICON:
                return self.icons.load_icon('application-default-icon',
                                            self.icon_size, 0)
            elif column == self.COL_INSTALLED:
                return False
            elif column == self.COL_AVAILABLE:
                return False
            elif column == self.COL_PKGNAME:
                return app.pkgname
            elif column == self.COL_RATING:
                return 0
            elif column == self.COL_NR_REVIEWS:
                return 0
            elif column == self.COL_IS_ACTIVE:
                if app.request:
                    # this may be wrong, but we don't want to do any checks at this moment
                    return (rowref == self.active_app)
                # This ensures the missing package will not expand
                return False
            elif column == self.COL_EXISTS:
                if app.request:
                    return True
                return False
            elif column == self.COL_ACTION_IN_PROGRESS:
                return -1
            elif column == self.COL_ACCESSIBLE:
                return '%s\n%s' % (app.pkgname, _("Not found"))
            elif column == self.COL_REQUEST:
                return app.request

        # Otherwise the app should return app data normally.
        appname = doc.get_value(XAPIAN_VALUE_APPNAME)
        pkgname = self.db.get_pkgname(doc)
        #popcon = self.db.get_popcon(doc)
        app = Application(appname, pkgname)

        # ensure that any app.requests don't get lost
        if self.apps:
            for s_app in self.apps:
                if s_app.pkgname == pkgname:
                    app.request = s_app.request

        if column == self.COL_APP_NAME:
            return app.appname
        elif column == self.COL_TEXT:
            appname = app.appname
            summary = self.db.get_summary(doc)
            return "%s\n%s" % (appname, summary)
        elif column == self.COL_MARKUP:
            appname = Application.get_display_name(self.db, doc)
            summary = Application.get_display_summary(self.db, doc)
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, app.pkgname)
            s = "%s\n<small>%s</small>" % (
                gobject.markup_escape_text(appname),
                gobject.markup_escape_text(summary))
            return s
        elif column == self.COL_ICON:
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
                    elif self.db.get_icon_needs_download(doc):
                        self._download_icon_and_show_when_ready(self.cache, 
                                                                app.pkgname,
                                                                icon_file_name)
                        # display the missing icon while the real one downloads
                        self.icon_cache[icon_name] = self._appicon_missing_icon
            except glib.GError, e:
                LOG.debug("get_icon returned '%s'" % e)
            return self._appicon_missing_icon
        elif column == self.COL_INSTALLED:
            pkgname = app.pkgname
            if pkgname in self.cache and self.cache[pkgname].is_installed:
                return True
            return False
        elif column == self.COL_AVAILABLE:
            pkgname = app.pkgname
            return pkgname in self.cache
        elif column == self.COL_PKGNAME:
            pkgname = app.pkgname
            return pkgname
        elif column == self.COL_RATING:
            stats = self.review_loader.get_review_stats(app)
            if stats:
                return stats.ratings_average
            return 0
        elif column == self.COL_NR_REVIEWS:
            stats = self.review_loader.get_review_stats(app)
            if stats:
                return stats.ratings_total
            return 0
        elif column == self.COL_IS_ACTIVE:
            return (rowref == self.active_app)
        elif column == self.COL_ACTION_IN_PROGRESS:
            if app.pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[app.pkgname].progress
            else:
                return -1
        elif column == self.COL_EXISTS:
            return True
        elif column == self.COL_ACCESSIBLE:
            pkgname = app.pkgname
            appname = app.appname
            summary = self.db.get_summary(doc)
            if pkgname in self.cache and self.cache[pkgname].is_installed:
                return "%s\n%s\n%s" % (appname, _('Installed'), summary)
            return "%s\n%s\n%s" % (appname, _('Not Installed'), summary) 
        elif column == self.COL_REQUEST:
            return app.request
    def on_iter_next(self, rowref):
        #LOG.debug("on_iter_next: %s" % rowref)
        new_rowref = int(rowref) + 1
        if new_rowref >= len(self.matches):
            return None
        return new_rowref
    def on_iter_children(self, parent):
        if parent:
            return None
        # rowref of the first element, so we return zero here
        return 0
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        return len(self.matches)
    def on_iter_nth_child(self, parent, n):
        #LOG.debug("on_iter_nth_child: %s %i" % (parent, n))
        if parent:
            return 0
        if n >= len(self.matches):
            return None
        return n
    def on_iter_parent(self, child):
        return None
