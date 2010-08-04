# Copyright (C) 2009 Canonical
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

from __future__ import with_statement


import __builtin__
import apt
import gettext
import glib
import gobject
import gtk
import locale
import logging
import math
import os
import pango
import string
import sys
import time
import xapian
import cairo

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.db.database import StoreDatabase, Application
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.paths import SOFTWARE_CENTER_ICON_CACHE_DIR
from softwarecenter.distro import get_distro
from widgets.mkit import get_em_value
from gtk import gdk

from gettext import gettext as _

# cache icons to speed up rendering
_app_icon_cache = {}


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
     COL_POPCON,
     COL_IS_ACTIVE,
     COL_ACTION_IN_PROGRESS,
     COL_EXISTS,
     COL_ACCESSIBLE) = range(12)

    column_type = (str,
                   str,
                   str,
                   gtk.gdk.Pixbuf,
                   bool,
                   bool,
                   str,
                   int,
                   bool,
                   int,
                   bool,
                   str)

    ICON_SIZE = 24
    MAX_STARS = 5

    # the default result size for a search
    DEFAULT_SEARCH_LIMIT = 200

    def __init__(self, cache, db, icons, search_query=None, 
                 limit=DEFAULT_SEARCH_LIMIT,
                 sortmode=SORT_UNSORTED, filter=None, exact=False,
                 icon_size=ICON_SIZE, global_icon_cache=True, 
                 nonapps_visible=False):
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
        - `exact`: If true, indexes of queries without matches will be
                    maintained in the store (useful to show e.g. a row
                    with "??? not found")
        """
        gtk.GenericTreeModel.__init__(self)
        self._logger = logging.getLogger("softwarecenter.view.appstore")
        self.search_query = search_query
        self.cache = cache
        self.db = db
        self.icons = icons
        self.icon_size = icon_size
        if global_icon_cache:
            self.icon_cache = _app_icon_cache
        else:
            self.icon_cache = {}

        # invalidate the cache on icon theme changes
        self.icons.connect("changed", self._clear_app_icon_cache)
        self._appicon_missing_icon = self.icons.load_icon(MISSING_APP_ICON, self.icon_size, 0)
        self.apps = []
        # this is used to re-set the cursor
        self.app_index_map = {}
        # this is used to find the in-progress rows
        self.pkgname_index_map = {}
        self.sortmode = sortmode
        self.filter = filter
        self.exact = exact
        self.active = True
        # These track if technical (non-applications) are being displayed
        # and if the user explicitly requested they be.
        self.nonapps_visible = nonapps_visible
        self.nonapp_pkgs = 0
        self._explicit_nonapp_visibility = False
        # backend stuff
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        # rowref of the active app and last active app
        self.active_app = None
        self._prev_active_app = 0
        self.limit = limit
        self.filter = filter
        # no search query means "all"
        if not search_query:
            search_query = xapian.Query("ATapplication")
            self.sortmode = SORT_BY_ALPHABET
            self.limit = 0

        # we support single and list search_queries,
        # if list we append them one by one
        if isinstance(search_query, xapian.Query):
            search_query = [search_query]
        self.search_query = search_query
        with ExecutionTime("populate model from query"):
            self._perform_search()

    def _perform_search(self):
        already_added = set()
        for q in self.search_query:
            self._logger.debug("using query: '%s'" % q)
            enquire = xapian.Enquire(self.db.xapiandb)
            if not self.nonapps_visible:
                enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                 q, xapian.Query("ATapplication")))

                matches = enquire.get_mset(0, len(self.db))
                self.nonapp_pkgs = matches.get_matches_estimated()
                q = xapian.Query(xapian.Query.OP_AND, 
                                 xapian.Query("ATapplication"), q)
            enquire.set_query(q)

            # set sort order
            if self.sortmode == SORT_BY_CATALOGED_TIME:
                if "catalogedtime" in self.db._axi_values:
                    enquire.set_sort_by_value(
                        self.db._axi_values["catalogedtime"], reverse=True)
                else:
                    logging.warning("no catelogedtime in axi")
            elif self.sortmode == SORT_BY_SEARCH_RANKING:
                # the default is to sort by popcon
                k = "SOFTWARE_CENTER_SEARCHES_SORT_MODE"
                if k in os.environ and os.environ[k] != "popcon":
                    pass
                else:
                    enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
                    
            # set limit
            if self.limit == 0:
                matches = enquire.get_mset(0, len(self.db))
            else:
                matches = enquire.get_mset(0, self.limit)
            self._logger.debug("found ~%i matches" % matches.get_matches_estimated())
            app_index = 0
            for m in matches:
                doc = m[xapian.MSET_DOCUMENT]
                if "APPVIEW_DEBUG_TERMS" in os.environ:
                    print doc.get_value(XAPIAN_VALUE_APPNAME)
                    for t in doc.termlist():
                        print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
                    print "\n"
                appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                pkgname = self.db.get_pkgname(doc)
                if self.filter and self.is_filtered_out(self.filter, doc):
                    continue
                # when doing multiple queries we need to ensure
                # we don't add duplicates
                popcon = self.db.get_popcon(doc)
                app = Application(appname, pkgname, popcon)
                if not app in already_added:
                    if self.sortmode == SORT_BY_ALPHABET:
                        self._insert_app_sorted(app)
                    else:
                        self._append_app(app)
                    already_added.add(app)
                # keep the UI going
                while gtk.events_pending():
                    gtk.main_iteration()
            if len(matches) == 0 and self.exact:
                # Find and remove a AP search prefix to get the
                # original package name of the xapian query.
                pkgname = ""
                for term in q:
                    if term.startswith("AP"):
                        pkgname = term[2:]
                        break
                app = Application("", pkgname)

                self.apps.append(app)
                
        # if we only have nonapps to be displayed, don't hide them
        if (not self.nonapps_visible and
            self.nonapp_pkgs > 0 and
            len(self.apps) == 0):
            self.nonapps_visible = True
            self._perform_search()
            
        # in the case where the app list is sorted, we must rebuild
        # the app_index_map and app_package_maps after the app list
        # has been fully populated (since only now will be know the
        # actual final indices)
        if self.sortmode == SORT_BY_ALPHABET:
            self._rebuild_index_maps()
        
        # This is data for store contents that will be generated
        # when called for externally. (see _refresh_contents_data)
        self._existing_apps = None
        self._installable_apps = None
        
    def _rebuild_index_maps(self):
        self.app_index_map.clear()
        self.pkgname_index_map.clear()
        app = None
        for i in range(len(self.apps)):
            app = self.apps[i]
            self.app_index_map[app] = i
            if not app.pkgname in self.pkgname_index_map:
                self.pkgname_index_map[app.pkgname] = []
            self.pkgname_index_map[app.pkgname].append(i)

    def _clear_app_icon_cache(self, theme):
        self.icon_cache.clear()

    # internal API
    def _append_app(self, app):
        """ append a application to the current store, keep 
            index maps up-to-date
        """
        self.apps.append(app)
        i = len(self.apps) - 1
        self.app_index_map[app] = i
        if not app.pkgname in self.pkgname_index_map:
            self.pkgname_index_map[app.pkgname] = []
        self.pkgname_index_map[app.pkgname].append(i)
        self.row_inserted(i, self.get_iter(i))

    def _insert_app_sorted(self, app):
        """ insert a application into a already sorted store
            at the right place
        """
        #print "adding: ", app
        l = 0
        r = len(self.apps) - 1
        while r >= l:
            m = (r+l) / 2
            #print "it: ", l, r, m
            if app < self.apps[m]:
                r = m - 1
            else:
                l = m + 1
        # we have a element 
        #print "found at ", l, r, m
        self._insert_app(app, l)

    def _insert_app(self, app, i):
        """ insert application at the given position and update
            the index maps
        """
        #print "old: ", [x.pkgname for x in self.apps]
        self.apps.insert(i, app)
        self.row_inserted(i, self.get_iter(i))
        #print "new: ", [x.pkgname for x in self.apps]

    # external API
    def clear(self):
        """Clear the store and disconnect all callbacks to allow it to be
        deleted."""
        self.backend.disconnect_by_func(self._on_transaction_finished)
        self.backend.disconnect_by_func(self._on_transaction_started)
        self.backend.disconnect_by_func(self._on_transaction_progress_changed)
        self.icons.disconnect_by_func(self._clear_app_icon_cache)
        self.apps = []
        self.app_index_map.clear()
        self.pkgname_index_map.clear()

    def update(self, appstore):
        """ update this appstore to match data from another """
        # Updating instead of replacing prevents a distracting white
        # flash. First, match list of apps.
        to_update = min(len(self), len(appstore))
        for i in range(to_update):
            self.apps[i] = appstore.apps[i]
            self.row_changed(i, self.get_iter(i))

        to_remove = max(0, len(self) - len(appstore))
        for i in range(to_remove):
            self.apps.pop()
            self.row_deleted(len(self))

        to_add = max(0, len(appstore) - len(self))
        apps_to_add = appstore.apps[len(appstore) - to_add:]
        for app in apps_to_add:
            path = len(self)
            self.apps.append(app)
            self.row_inserted(path, self.get_iter(path))
            
        self._rebuild_index_maps()

        # Next, match data about the store.
        self.cache = appstore.cache
        self.db = appstore.db
        self.icons = appstore.icons
        self.search_query = appstore.search_query
        self.sortmode = appstore.sortmode
        self.filter = appstore.filter
        self.exact = appstore.exact
        self.nonapps_visible = appstore.nonapps_visible
        self.nonapp_pkgs = appstore.nonapp_pkgs
        self._existing_apps = appstore._existing_apps
        self._installable_apps = appstore._installable_apps

        # Re-claim the memory used by the new appstore
        appstore.clear()

    def _refresh_contents_data(self):
        # Quantitative data on stored packages. This generates the information.
        exists = lambda app: app.pkgname in self.cache
        installable = lambda app: (not self.cache[app.pkgname].is_installed
                                   and app.pkgname not in
                                   self.backend.pending_transactions)
        self._existing_apps = __builtin__.filter(exists, self.apps)
        self._installable_apps = __builtin__.filter(installable,
                                                    self.existing_apps)

    def _get_existing_apps(self):
        if self._existing_apps == None:
            self._refresh_contents_data()
        return self._existing_apps

    def _get_installable_apps(self):
        if self._installable_apps == None:
            self._refresh_contents_data()
        return self._installable_apps

    # data about the visible contents of the store, generated on call.
    existing_apps = property(_get_existing_apps)
    installable_apps = property(_get_installable_apps)

    def is_filtered_out(self, filter, doc):
        """ apply filter and return True if the package is filtered out """
        pkgname = self.db.get_pkgname(doc)
        return not filter.filter(doc, pkgname)
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
        if (not self.apps or
            not self.active or
            not pkgname in self.pkgname_index_map):
            return
        for index in self.pkgname_index_map[pkgname]:
            row = self[index]
            self.row_changed(row.path, row.iter)

    # the following methods ensure that the contents data is refreshed
    # whenever a transaction potentially changes it: see _refresh_contents.

    def _on_transaction_started(self, *args):
        self._existing_apps = None
        self._installable_apps = None

    def _on_transaction_finished(self, *args):
        self._existing_apps = None
        self._installable_apps = None

    # GtkTreeModel functions
    def on_get_flags(self):
        return (gtk.TREE_MODEL_LIST_ONLY|
                gtk.TREE_MODEL_ITERS_PERSIST)
    def on_get_n_columns(self):
        return len(self.column_type)
    def on_get_column_type(self, index):
        return self.column_type[index]
    def on_get_iter(self, path):
        #self._logger.debug("on_get_iter: %s" % path)
        if len(self.apps) == 0:
            return None
        index = path[0]
        return index
    def on_get_path(self, rowref):
        self._logger.debug("on_get_path: %s" % rowref)
        return rowref
    def on_get_value(self, rowref, column):
        #self._logger.debug("on_get_value: %s %s" % (rowref, column))
        try:
            app = self.apps[rowref]
        except IndexError:
            self._logger.exception("on_get_value: rowref=%s apps=%s" % (rowref, self.apps))
            return
        try:
            doc = self.db.get_xapian_document(app.appname, app.pkgname)
        except IndexError:
            # This occurs when using custom lists, which keep missing package
            # names in the record. In this case a "Not found" cell should be
            # rendered, with all data but package name absent and the text
            # markup colored gray.
            if column == self.COL_APP_NAME:
                return _("Not found")
            elif column == self.COL_TEXT:
                return "%s\n" % app.pkgname
            elif column == self.COL_MARKUP:
                s = "<span foreground='#666'>%s\n<small>%s</small></span>" % (
                    gobject.markup_escape_text(_("Not found")),
                    gobject.markup_escape_text(app.pkgname))
                return s
            elif column == self.COL_ICON:
                return self.icons.load_icon(MISSING_PKG_ICON,
                                            self.icon_size, 0)
            elif column == self.COL_INSTALLED:
                return False
            elif column == self.COL_AVAILABLE:
                return False
            elif column == self.COL_PKGNAME:
                return app.pkgname
            elif column == self.COL_POPCON:
                return 0
            elif column == self.COL_IS_ACTIVE:
                # This ensures the missing package will not expand
                return False
            elif column == self.COL_EXISTS:
                return False
            elif column == self.COL_ACTION_IN_PROGRESS:
                return -1
            elif column == self.COL_ACCESSIBLE:
                return '%s\n%s' % (app.pkgname, _('Package state unknown'))

        # Otherwise the app should return app data normally.
        if column == self.COL_APP_NAME:
            return app.appname
        elif column == self.COL_TEXT:
            appname = app.appname
            summary = self.db.get_summary(doc)
            return "%s\n%s" % (appname, summary)
        elif column == self.COL_MARKUP:
            appname = app.appname
            summary = self.db.get_summary(doc)
            # SPECIAL CASE: the spec says that when there is no appname, 
            #               the summary should be displayed as appname
            if not appname:
                appname = summary
                summary = app.pkgname
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
                    
                    # check if this is a downloadable icon
                    if self.db.get_icon_needs_download(doc):
                        print "icon is downloadable: ", icon_file_name
                        # first check our local downloaded icon cache directory
                        # FIXME:  move this code into a common location (utils?  new class?) for use by appdetailsview also
                        # FIXME:  limit to a single download attempt for a given icon filename
                        icon_file = os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR, icon_file_name)
                        if os.path.exists(icon_file):
                            print "found the icon in the local cache"
                            pb = gtk.gdk.pixbuf_new_from_file_at_size(icon_file,
                                                                        self.icon_size,
                                                                        self.icon_size)
                            self.icon_cache[icon_name] = pb
                            return pb
                        else:
                            # if not in the local icon cache directory, need to download it
                            print "did not find the icon, must download it"
                            # FIXME:  don't hardcode the PPA name
                            # url = self.distro.PPA_DOWNLOADABLE_ICON_URL % ("app-review-board", icon_file_name)
                            url = "http://ppa.launchpad.net/%s/meta/ppa/%s" % ("app-review-board", icon_file_name)
                            
                            image_downloader = ImageDownloader()
                            image_downloader.connect('image-url-reachable', self._on_image_url_reachable)
                            image_downloader.connect('image-download-complete', self._on_image_download_complete)
                            image_downloader.download_image(url, icon_file)
                            
                            # it's downloading asynchronously, so for now we show the appicon missing icon
                            self.icon_cache[icon_name] = self._appicon_missing_icon
                            return self._appicon_missing_icon
                    else:
                        # load the icon from the theme
                        icon = self.icons.load_icon(icon_name, self.icon_size, 0)
                        self.icon_cache[icon_name] = icon
                        return icon
            except glib.GError, e:
                self._logger.debug("get_icon returned '%s'" % e)
                self.icon_cache[icon_name] = self._appicon_missing_icon
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
        elif column == self.COL_POPCON:
            return self._calc_normalized_rating(self.apps[rowref].popcon)
        elif column == self.COL_IS_ACTIVE:
            return (rowref == self.active_app)
        elif column == self.COL_ACTION_IN_PROGRESS:
            if app.pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[app.pkgname]
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

    def on_iter_next(self, rowref):
        #self._logger.debug("on_iter_next: %s" % rowref)
        new_rowref = int(rowref) + 1
        if new_rowref >= len(self.apps):
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
        self._logger.debug("on_iter_n_children: %s (%i)" % (rowref, len(self.apps)))
        if rowref:
            return 0
        return len(self.apps)
    def on_iter_nth_child(self, parent, n):
        self._logger.debug("on_iter_nth_child: %s %i" % (parent, n))
        if parent:
            return 0
        if n >= len(self.apps):
            return None
        return n
    def on_iter_parent(self, child):
        return None
        
    def _on_image_url_reachable(self, downloader, reachable):
        print "called _on_image_url_reachable with reachable: ", reachable
    
    def _on_image_download_complete(self, downloader, image_file_path):
        print "called _on_image_download_complete with image_file_path: ", image_file_path


class CellRendererButton2:

    def __init__(self, name, markup=None, markup_variants=None, xpad=12, ypad=4, use_max_variant_width=True):
        # use_max_variant_width is currently ignored. assumed to be True

        self.name = name

        self.current_variant = 0
        if markup:
            self.markup_variants = (markup,)
        else:
            # expects a list or tuple!
            self.markup_variants = markup_variants

        self.xpad = xpad
        self.ypad = ypad
        self.allocation = gdk.Rectangle(0,0,1,1)
        self.state = gtk.STATE_NORMAL
        self.has_focus = False

        self._widget = None
        self._geometry = None
        return

    def _layout_reset(self, layout):
        layout.set_width(-1)
        layout.set_ellipsize(pango.ELLIPSIZE_NONE)
        return

    def configure_geometry(self, widget):
        if self._geometry: return
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)
        max_w = 0
        for variant in self.markup_variants:
            layout.set_markup(gobject.markup_escape_text(variant))
            max_size = max(self.get_size(), layout.get_pixel_extents()[1][2:])

        w, h = max_size
        self.set_size(w+2*self.xpad, h+2*self.ypad)
        self._geometry = True
        return

    def scrub_geometry(self):
        self._geometry = None
        return

    def point_in(self, x, y):
        return gdk.region_rectangle(self.allocation).point_in(x,y)

    def get_size(self):
        a = self.allocation
        return a.width, a.height 

    def set_position(self, x, y):
        a = self.allocation
        self.size_allocate(gdk.Rectangle(x, y, a.width, a.height))
        return

    def set_size(self, w, h):
        a = self.allocation
        self.size_allocate(gdk.Rectangle(a.x, a.y, w, h))
        return

    def size_allocate(self, rect):
        self.allocation = rect
        return

    def set_state(self, state):
        if state == self.state: return
        self.state = state
        if self._widget:
            self._widget.queue_draw_area(*self.get_allocation_tuple())
        return

    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            self.state = gtk.STATE_NORMAL
        else:
            self.state = gtk.STATE_INSENSITIVE
        if self._widget:
            self._widget.queue_draw_area(*self.get_allocation_tuple())
        return

    def set_markup(self, markup):
        self.markup_variant = (markup,)
        return

    def set_markup_variants(self, markup_variants):
        # expects a tuple or list
        self.markup_variants = markup_variants
        return

    def set_markup_variant_n(self, n):
        # yes i know this is totally hideous...
        if n >= len(self.markup_variants):
            print n, 'Not in range', self.markup_variants
            return
        self.current_variant = n
        return

    def get_allocation_tuple(self):
        a = self.allocation
        return (a.x, a.y, a.width, a.height)

    def render(self, window, widget, layout=None):
        if not self._widget:
            self._widget = widget
        if self.state != gtk.STATE_ACTIVE:
            shadow = gtk.SHADOW_OUT
        else:
            shadow = gtk.SHADOW_IN

        if not layout:
            pc = widget.get_pango_context()
            layout = pango.Layout(pc)
        else:
            self._layout_reset(layout)

        layout.set_markup(self.markup_variants[self.current_variant])
        xpad, ypad = self.xpad, self.ypad
        x, y, w, h = self.get_allocation_tuple()

        # clear teh background first
        # this prevents the button overdrawing on its self,
        # which results in transparent pixels accumulating alpha value
        cr = window.cairo_create()
        cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.rectangle(x, y, w, h)
        cr.clip()
        cr.paint_with_alpha(0)

        cr.set_operator(cairo.OPERATOR_OVER)
        del cr
        widget.style.paint_box(window,
                               self.state,
                               shadow,
                               (x, y, w, h),
                               widget,
                               "button",
                               x, y, w, h)

        # if we have more than one markup variant
        # we need to calc layout x-offset for current variant markup
        if len(self.markup_variants) > 1:
            lw = layout.get_pixel_extents()[1][2]
            xo = x + (w - lw)/2

        # else, we can just use xpad as the x-offset... 
        else:
            xo = x + xpad

        if self.has_focus and self.state != gtk.STATE_INSENSITIVE and \
            self._widget.has_focus():
            widget.style.paint_focus(window,
                                     self.state,
                                     (x+2, y+2, w-4, h-4),
                                     widget,
                                     "expander",
                                     x+2, y+2,
                                     w-4, h-4)

        widget.style.paint_layout(window,
                                  self.state,
                                  True,
                                  (xo, y+ypad, w, h),
                                  widget,
                                  "button",
                                  xo, y+ypad,
                                  layout)
        return


# custom cell renderer to support dynamic grow
class CellRendererAppView2(gtk.CellRendererText):

    # offset of the install overlay icon
    OFFSET_X = 20
    OFFSET_Y = 20

    # size of the install overlay icon
    OVERLAY_SIZE = 16

    __gproperties__ = {
        'overlay' : (bool, 'overlay', 'show an overlay icon', False,
                     gobject.PARAM_READWRITE),

        'pixbuf' :  (gtk.gdk.Pixbuf, "Pixbuf", 
                    "Application icon pixbuf image", gobject.PARAM_READWRITE),

        # numbers mean: min: 0, max: 5, default: 0
        'rating': (gobject.TYPE_INT, 'Rating', 'Popcon rating', 0, 5, 0,
            gobject.PARAM_READWRITE),

        'isactive': (bool, 'IsActive', 'Is active?', False,
                    gobject.PARAM_READWRITE),

        'installed': (bool, 'installed', 'Is the app installed', False,
                     gobject.PARAM_READWRITE),

        'available': (bool, 'available', 'Is the app available for install', False,
                     gobject.PARAM_READWRITE),

        'action_in_progress': (gobject.TYPE_INT, 'Action Progress', 'Action progress', -1, 100, -1,
                     gobject.PARAM_READWRITE),

        'exists': (bool, 'exists', 'Is the app found in current channel', False,
                   gobject.PARAM_READWRITE),

        # overload the native markup property becasue i didnt know how to read it
        # note; the 'text' attribute is used as the cell atk description
        'markup': (str, 'markup', 'The markup to paint', '',
                   gobject.PARAM_READWRITE)
        }

    def __init__(self, show_ratings, overlay_icon_name):
        gtk.CellRendererText.__init__(self)
        # geometry-state values
        self.overlay_icon_name = overlay_icon_name
        self.pixbuf_width = 0
        self.normal_height = 0
        self.selected_height = 0

        # attributes
        self.overlay = False
        self.pixbuf = None
        self.markup = ''
        self.rating = 0
        self.isactive = False
        self.installed = False
        self.show_ratings = show_ratings

        # button packing
        self.button_spacing = 0
        self._buttons = {gtk.PACK_START: [],
                         gtk.PACK_END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = None

        # icon/overlay jazz
        icons = gtk.icon_theme_get_default()
        try:
            self._installed = icons.load_icon(overlay_icon_name,
                                              self.OVERLAY_SIZE, 0)
        except glib.GError:
            # icon not present in theme, probably because running uninstalled
            self._installed = icons.load_icon('emblem-system',
                                              self.OVERLAY_SIZE, 0)
        return

    def _layout_get_pixel_width(self, layout):
        return layout.get_pixel_extents()[1][2]

    def _layout_get_pixel_height(self, layout):
        return layout.get_pixel_extents()[1][3]

    def _render_icon(self, window, widget, cell_area, state, xpad, ypad, direction):
        # calc offsets so icon is nicely centered
        xo = (32 - self.pixbuf.get_width())/2
        yo = (32 - self.pixbuf.get_height())/2

        if direction != gtk.TEXT_DIR_RTL:
            x = xpad+xo
        else:
            x = cell_area.width-xpad+xo-32

        # draw appicon pixbuf
        window.draw_pixbuf(None,
                           self.pixbuf,             # icon
                           0, 0,                    # src pixbuf
                           x, cell_area.y+ypad+yo,  # dest in window
                           -1, -1,                  # size
                           0, 0, 0)                 # dither

        # draw overlay if application is installed
        if self.overlay:
            if direction != gtk.TEXT_DIR_RTL:
                x = self.OFFSET_X
            else:
                x = cell_area.width - self.OFFSET_X - self.OVERLAY_SIZE

            y = cell_area.y + self.OFFSET_Y
            window.draw_pixbuf(None,
                               self._installed,     # icon
                               0, 0,                # src pixbuf
                               x, y,                # dest in window
                               -1, -1,              # size
                               0, 0, 0)             # dither
        return

    def _render_appsummary(self, window, widget, cell_area, state, layout, xpad, ypad, direction):
        # adjust cell_area

        # work out max allowable layout width
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = cell_area.width - self.pixbuf_width - 3*xpad

        if self.isactive and self.props.action_in_progress > 0:
            action_btn = self.get_button_by_name('action0')
            if not action_btn:
                print 'No action button? This doesn\'t make sense!'
                return
            max_layout_width -= (xpad + action_btn.get_size()[0]) 

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*pango.SCALE)
            lw = max_layout_width

        if direction != gtk.TEXT_DIR_RTL:
            x, y = 2*xpad+self.pixbuf_width, cell_area.y+ypad
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad
            y = cell_area.y+ypad

        w, h = lw, self.normal_height
        widget.style.paint_layout(window, state,
                                  False,
                                  (x, y, w, h),
                                  widget, None,
                                  x, y, layout)
        return

    def _render_progress(self, window, widget, cell_area, ypad, direction):
        # as seen in gtk's cellprogress.c
        percent = self.props.action_in_progress * 0.01

        # per the spec, the progressbar should be the width of the action button
        action_btn = self.get_button_by_name('action0')
        if not action_btn:
            print 'No action button? This doesn\'t make sense!'
            return

        x, y, w, h = action_btn.get_allocation_tuple()
        # shift the bar to the top edge
        y = cell_area.y + ypad

#        FIXME: GtkProgressBar draws the box with "trough" detail,
#        but some engines don't paint anything with that detail for
#        non-GtkProgressBar widgets.

        widget.style.paint_box(window,
                               gtk.STATE_NORMAL,
                               gtk.SHADOW_IN,
                               (x, y, w, h),
                               widget,
                               None,
                               x, y, w, h)

        if direction != gtk.TEXT_DIR_RTL:
            clip = gdk.Rectangle(x, y, int((w)*percent), h)
        else:
            clip = gdk.Rectangle(x+(w-int(w*percent)), y, int(w*percent), h)

        widget.style.paint_box(window,
                               gtk.STATE_SELECTED,
                               gtk.SHADOW_OUT,
                               clip,
                               widget,
                               "bar",
                               clip.x, clip.y,
                               clip.width, clip.height)
        return

    def set_normal_height(self, h):
        self.normal_height = int(h)
        return

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w
        return

    def set_selected_height(self, h):
        self.selected_height = h
        return

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing
        return

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]
        return None

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.iteritems():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=gtk.PACK_START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn
        return

    def button_pack_start(self, btn):
        self.button_pack(btn, gtk.PACK_START)
        return

    def button_pack_end(self, btn):
        self.button_pack(btn, gtk.PACK_END)
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):

        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        direction = widget.get_direction()

        # important! ensures correct text rendering, esp. when using hicolor theme
        if (flags & gtk.CELL_RENDERER_SELECTED) != 0:
            state = gtk.STATE_SELECTED
        else:
            state = gtk.STATE_NORMAL

        if not self._layout:
            pc = widget.get_pango_context()
            self._layout = pango.Layout(pc)
            self._layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        self._render_icon(window, widget,
                          cell_area, state,
                          xpad, ypad,
                          direction)

        self._layout.set_markup(self.markup)
        self._render_appsummary(window, widget,
                                cell_area, state,
                                self._layout,
                                xpad, ypad,
                                direction)

        if not self.isactive:
            return

        if self.props.action_in_progress > 0:
            self._render_progress(window,
                                  widget,
                                  cell_area,
                                  ypad,
                                  direction)

        # layout buttons and paint
        y = cell_area.y+cell_area.height-ypad
        spacing = self.button_spacing

        if direction != gtk.TEXT_DIR_RTL:
            start = gtk.PACK_START
            end = gtk.PACK_END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = gtk.PACK_END
            end = gtk.PACK_START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.allocation.height)
            btn.render(window, widget, self._layout)
            xs += btn.allocation.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.allocation.width
            btn.set_position(xb, y-btn.allocation.height)
            btn.render(window, widget, self._layout)
            xb -= spacing
        return

    def do_get_size(self, widget, cell_area):
        if not self.isactive:
            return -1, -1, -1, self.normal_height
        return -1, -1, -1, self.selected_height

gobject.type_register(CellRendererAppView2)



class AppView(gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, str),
                                       ),
    }

    def __init__(self, show_ratings, store=None):
        gtk.TreeView.__init__(self)
        self._logger = logging.getLogger("softwarecenter.view.appview")
        #self.buttons = {}
        self.pressed = False
        self.focal_btn = None
        self._action_block_list = []

        # if this hacked mode is available everything will be fast
        # and we can set fixed_height mode and still have growing rows
        # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            self._logger.warn("ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # a11y: this is a cell renderer that only displays a icon, but still
        #       has a markup property for orca and friends
        # we use it so that orca and other a11y tools get proper text to read
        # it needs to be the first one, because that is what the tools look
        # at by default

        tr = CellRendererAppView2(show_ratings, "software-center-installed")
        tr.set_pixbuf_width(32)
        tr.set_button_spacing(3)

        # translatable labels for cell buttons
        # string for info button, currently does not need any variants
        self._info_str = _('More Info')

        # string for action button
        # needs variants for the current label states: install, remove & pending
        self._action_strs = {'install' : _('Install'),
                             'remove'  : _('Remove')}

        # create buttons and set initial strings
        info = CellRendererButton2(name='info', markup=self._info_str)
        variants = (self._action_strs['install'],
                    self._action_strs['remove'])
        action = CellRendererButton2(name='action0', markup_variants=variants)

        tr.button_pack_start(info)
        tr.button_pack_end(action)

        column = gtk.TreeViewColumn("Available Apps", tr,
                                    pixbuf=AppStore.COL_ICON,
                                    overlay=AppStore.COL_INSTALLED,
                                    text=AppStore.COL_ACCESSIBLE,
                                    markup=AppStore.COL_MARKUP,
                                    rating=AppStore.COL_POPCON,
                                    isactive=AppStore.COL_IS_ACTIVE,
                                    installed=AppStore.COL_INSTALLED, 
                                    available=AppStore.COL_AVAILABLE,
                                    action_in_progress=AppStore.COL_ACTION_IN_PROGRESS,
                                    exists=AppStore.COL_EXISTS)

        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        if store is None:
            store = gtk.ListStore(str, gtk.gdk.Pixbuf)
        self.set_model(store)

        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, tr)

        # button and motion are "special"
        self.connect("style-set", self._on_style_set, tr)

        self.connect("button-press-event", self._on_button_press_event, tr)
        self.connect("button-release-event", self._on_button_release_event, tr)

        self.connect("key-press-event", self._on_key_press_event, tr)
        self.connect("key-release-event", self._on_key_release_event, tr)

        self.connect("cursor-changed", self._on_cursor_changed, tr)
        self.connect("motion-notify-event", self._on_motion, tr)

        self.backend = get_install_backend()
        self._transactions_connected = False
        self.connect('realize', self._on_realize, tr)

    def set_model(self, new_model):
        # unset
        if new_model is None:
            super(AppView, self).set_model(None)
        # Only allow use of an AppStore model
        if type(new_model) != AppStore:
            return
        model = self.get_model()
        # If there is no current model, simply set the new one.
        if not model:
            return super(AppView, self).set_model(new_model)
        # if the changes are too big set a new model instead of using
        # "update" - the rational is that GtkTreeView is really slow
        # if thousands of rows are added at once on a "connected" model
        if abs(len(new_model)-len(model)) > AppStore.DEFAULT_SEARCH_LIMIT:
            return super(AppView, self).set_model(new_model)
        return model.update(new_model)
        
    def clear_model(self):
        self.set_model(None)

    def is_action_in_progress_for_selected_app(self):
        """
        return True if an install or remove of the current package
        is in progress
        """
        (path, column) = self.get_cursor()
        model = self.get_model()
        return (model[path][AppStore.COL_ACTION_IN_PROGRESS] != -1)

    def get_button(self, key):
        return self.buttons[key]

    def _on_realize(self, widget, tr):
        # connect to backend events once self is realized so handlers 
        # have access to the TreeView's initialised gtk.gdk.Window
        if self._transactions_connected: return
        self.backend.connect("transaction-started", self._on_transaction_started, tr)
        self.backend.connect("transaction-finished", self._on_transaction_finished, tr)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped, tr)
        self._transactions_connected = True
        return

    def _on_style_set(self, widget, old_style, tr):
        em = get_em_value()

        tr.set_property('xpad', int(em*0.5+0.5))
        tr.set_property('ypad', int(em*0.5+0.5))

        normal_height = int(2.75*em+0.5 + 2*tr.get_property('ypad'))
        tr.set_normal_height(normal_height)
        tr.set_selected_height(int(normal_height + 3*em))

        for btn in tr.get_buttons():
            # reset cached button geometry (x, y, w, h)
            btn.scrub_geometry()
            # recalc button geometry and cache
            btn.configure_geometry(self)
        return

    def _on_motion(self, tree, event, tr):
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y):
            self.window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path: return

        use_hand = False
        for btn in tr.get_buttons():
            if btn.state != gtk.STATE_INSENSITIVE:
                if btn.point_in(x, y):
                    if self.focal_btn is btn:
                        use_hand = True
                        btn.set_state(gtk.STATE_ACTIVE)
                    elif not self.pressed:
                        use_hand = True
                        btn.set_state(gtk.STATE_PRELIGHT)
                else:
                    if btn.state != gtk.STATE_NORMAL:
                        btn.set_state(gtk.STATE_NORMAL)

        if use_hand:
            self.window.set_cursor(self._cursor_hand)
        else:
            self.window.set_cursor(None)
        return

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0] or (0,)
        sel.select_path(path)
        self._update_selected_row(view, tr)

    def _update_selected_row(self, view, tr):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows: 
            return False

        row = rows[0][0]
        # update active app, use row-ref as argument
        model._set_active_app(row)
        installed = model[row][AppStore.COL_INSTALLED]
        action_btn = tr.get_button_by_name('action0')
        #if not action_btn: return False

        if self.is_action_in_progress_for_selected_app():
            action_btn.set_sensitive(False)
        elif self.pressed and self.focal_btn == action_btn:
            action_btn.set_state(gtk.STATE_ACTIVE)
        else:
            action_btn.set_state(gtk.STATE_NORMAL)

        if installed:
            action_btn.set_markup_variant_n(1)
            #action_btn.configure_geometry(self)
        else:
            action_btn.set_markup_variant_n(0)
            #action_btn.configure_geometry(self)

        name = model[row][AppStore.COL_APP_NAME]
        pkgname = model[row][AppStore.COL_PKGNAME]
        popcon = model[row][AppStore.COL_POPCON]
        self.emit("application-selected", Application(name, pkgname, popcon))
        return False

    def _on_row_activated(self, view, path, column, tr):
        pointer = gtk.gdk.device_get_core_pointer()
        x, y = pointer.get_state(view.window)[0]
        for btn in tr.get_buttons():
            if btn.point_in(int(x), int(y)): return

        model = view.get_model()
        exists = model[path][AppStore.COL_EXISTS]
        if exists:
            name = model[path][AppStore.COL_APP_NAME]
            pkgname = model[path][AppStore.COL_PKGNAME]
            popcon = model[path][AppStore.COL_POPCON]
            self.emit("application-activated", Application(name, pkgname, popcon))

    def _on_button_press_event(self, view, event, tr):
        if event.button != 1:
            return
        self.pressed = True
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        path = res[0]
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != gtk.STATE_INSENSITIVE):
                self.focal_btn = btn
                btn.set_state(gtk.STATE_ACTIVE)
                return
        self.focal_btn = None

    def _on_button_release_event(self, view, event, tr):
        if event.button != 1:
            return
        self.pressed = False
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        path = res[0]
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != gtk.STATE_INSENSITIVE):
                btn.set_state(gtk.STATE_NORMAL)
                self.window.set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                break
        self.focal_btn = None

    def _on_key_press_event(self, widget, event, tr):
        kv = event.keyval
        #print kv
        r = False
        if kv == gtk.keysyms.Right: # right-key
            btn = tr.get_button_by_name('action0')
            if btn.state != gtk.STATE_INSENSITIVE:
                btn.has_focus = True
                btn = tr.get_button_by_name('info')
                btn.has_focus = False
        elif kv == gtk.keysyms.Left: # left-key
            btn = tr.get_button_by_name('action0')
            btn.has_focus = False
            btn = tr.get_button_by_name('info')
            btn.has_focus = True
        elif kv == gtk.keysyms.space:  # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != gtk.STATE_INSENSITIVE:
                    btn.set_state(gtk.STATE_ACTIVE)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    #print model[path][AppStore.COL_APP_NAME]
                    if path:
                        #self._init_activated(btn, self.get_model(), path)
                        r = True
                    break

        self.queue_draw()
        return r

    def _on_key_release_event(self, widget, event, tr):
        kv = event.keyval
        r = False
        if kv == 32:    # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != gtk.STATE_INSENSITIVE:
                    btn.set_state(gtk.STATE_NORMAL)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    #print model[path][AppStore.COL_APP_NAME]
                    if path:
                        self._init_activated(btn, self.get_model(), path)
                        btn.has_focus = False
                        r = True
                    break

        self.queue_draw()
        return r

    def _init_activated(self, btn, model, path):

        appname = model[path][AppStore.COL_APP_NAME]
        pkgname = model[path][AppStore.COL_PKGNAME]
        installed = model[path][AppStore.COL_INSTALLED]
        popcon = model[path][AppStore.COL_POPCON]

        s = gtk.settings_get_default()
        gobject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self._app_activated_cb,
                            btn,
                            btn.name,
                            appname,
                            pkgname,
                            popcon,
                            installed,
                            model,
                            path)
        return

    def _app_activated_cb(self, btn, btn_id, appname, pkgname, popcon, installed, store, path):
        if btn_id == 'info':
            self.emit("application-activated", Application(appname, pkgname, popcon))
        elif btn_id == 'action0':
            btn.set_sensitive(False)
            store.row_changed(path[0], store.get_iter(path[0]))
            # be sure we dont request an action for a pkg with pre-existing actions
            if pkgname in self._action_block_list:
                print 'Action already in progress for package: %s' % pkgname
                return
            self._action_block_list.append(pkgname)
            if installed:
                perform_action = APP_ACTION_REMOVE
            else:
                perform_action = APP_ACTION_INSTALL
            self.emit("application-request-action", Application(appname, pkgname, popcon), perform_action)
        return False

    def _set_cursor(self, btn, cursor):
        pointer = gtk.gdk.device_get_core_pointer()
        x, y = pointer.get_state(self.window)[0]
        if btn.point_in(int(x), int(y)):
            self.window.set_cursor(cursor)

    def _on_transaction_started(self, backend, tr):
        """ callback when an application install/remove transaction has started """
        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            action_btn.set_sensitive(False)
            self._set_cursor(action_btn, None)

    def _on_transaction_finished(self, backend, pkgname, success, tr):
        """ callback when an application install/remove transaction has finished """
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(pkgname)

        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _on_transaction_stopped(self, backend, pkgname, tr):
        """ callback when an application install/remove transaction has stopped """
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(pkgname)

        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            # this should be a function that decides action button state label...
            if action_btn.current_variant == 2:
                action_btn.set_markup_variant_n(1)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _check_remove_pkg_from_blocklist(self, pkgname):
        if pkgname in self._action_block_list:
            i = self._action_block_list.index(pkgname)
            del self._action_block_list[i]

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]


# XXX should we use a xapian.MatchDecider instead?
class AppViewFilter(object):
    """
    Filter that can be hooked into AppStore to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        self.distro = get_distro()
        self.db = db
        self.cache = cache
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
        self.only_packages_without_applications = False
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def get_supported_only(self):
        return self.supported_only
    def set_only_packages_without_applications(self, v):
        """
        only show packages that are not displayed as applications

        e.g. abiword (the package document) will not be displayed
             because there is a abiword application already
        """
        self.only_packages_without_applications = v
    def get_only_packages_without_applications(self, v):
        return self.only_packages_without_applications
    def filter(self, doc, pkgname):
        """return True if the package should be displayed"""
        #self._logger.debug("filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.only_packages_without_applications:
            if not doc.get_value(XAPIAN_VALUE_PKGNAME):
                # "if not self.db.xapiandb.postlist("AP"+pkgname):"
                # does not work for some reason
                for m in self.db.xapiandb.postlist("AP"+pkgname):
                    return False
        if self.installed_only:
            if (not pkgname in self.cache or
                not self.cache[pkgname].is_installed):
                return False
        if self.not_installed_only:
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                return False
        if self.supported_only:
            if not self.distro.is_supported(self.cache, doc, pkgname):
                return False
        return True

def get_query_from_search_entry(search_term):
    # now build a query
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    # ensure that we only search for applicatins here, even
    # when a-x-i is loaded
    app_query =  xapian.Query("ATapplication")
    query = xapian.Query(xapian.Query.OP_AND, app_query, user_query)
    return query

def on_entry_changed(widget, data):
    new_text = widget.get_text()
    #if len(new_text) < 3:
    #    return
    (cache, db, view) = data
    query = get_query_from_search_entry(new_text)
    view.set_model(AppStore(cache, db, icons, query))
    with ExecutionTime("model settle"):
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    # the store
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.prepend_search_path("/usr/share/app-install/icons/")
    icons.prepend_search_path("/usr/share/software-center/icons/")

    # now the store
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(False)
    store = AppStore(cache, db, icons, sort=True, filter=filter)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (cache, db, view))
    entry.set_text("f")

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400, 400)
    win.show_all()

    gtk.main()

