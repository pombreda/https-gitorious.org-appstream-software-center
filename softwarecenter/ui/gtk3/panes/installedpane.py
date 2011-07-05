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

import apt
import gettext
from gi.repository import Gtk
import logging
import os
import sys
import xapian
from gi.repository import GObject

from gettext import gettext as _

from softwarecenter.enums import NonAppVisibility, NavButtons, ViewPages, SortMethods
from softwarecenter.utils import wait_for_apt_cache_ready

from softwarepane import SoftwarePane

from views.appview import AppView, AppViewFilter
from softwarecenter.ui.gtk3.models.appstore2 import AppTreeStore

from softwarecenter.db.categories import (Category,
                                          CategoriesParser,
                                          categories_sorted_by_name)

from softwarecenter.ui.gtk3.models.appstore2 import AppEnquire, AppTreeStore, CategoryRowReference
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager


def interrupt_build_and_wait(f):
    """ decorator that ensures that a build of the categorised installed apps
        is interrupted before a new build commences.
        expects self._build_in_progress and self._halt_build as properties
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        if self._build_in_progress:
            print 'Waiting for build to exit...'
            self._halt_build = True
            GObject.timeout_add(200, lambda: wrapper(*args, **kwargs))
            return False
        # ready now
        self._halt_build = False
        f(*args, **kwargs)
        return False
    return wrapper


class InstalledPages:
    (LIST,
     DETAILS) = range(2)


class InstalledPane(SoftwarePane, CategoriesParser):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """
     
    __gsignals__ = {'installed-pane-created':(GObject.SignalFlags.RUN_FIRST,
                                              None,
                                              ())}

    def __init__(self, cache, db, distro, icons, datadir):
        # store
        store = AppTreeStore(db, cache, icons)

        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        CategoriesParser.__init__(self, db)

        self.current_appview_selection = None
        self.loaded = False
        self.pane_name = _("Installed Software")

        # state
        self.state.filter = AppViewFilter(db, cache)
        self.state.filter.set_installed_only(True)

        self.installed_apps = 0

        # switches to terminate build in progress
        self._build_in_progress = False
        self._halt_build = False

        self.nonapps_visible = NonAppVisibility.NEVER_VISIBLE

        # init view in the background after a short delay
        GObject.timeout_add(2000, self.init_view)

    def init_view(self):
        if self.view_initialized: return

        SoftwarePane.init_view(self)
        print 'initing stuff'

        self.label_app_list_header.set_no_show_all(True)
        self.notebook.append_page(self.box_app_list, Gtk.Label(label="installed"))

        # details
        self.notebook.append_page(self.scroll_details, Gtk.Label(label="details"))
        # initial refresh
        self.state.search_term = ""

        # build models and filters
        self.base_model = AppTreeStore(self.db, self.cache, self.icons)

        self.treefilter = self.base_model.filter_new(None)
        self.treefilter.set_visible_func(self._row_visibility_func,
                                         AppTreeStore.COL_ROW_DATA)
        self.app_view.set_model(self.treefilter)
        self.app_view.connect("row-collapsed", self._on_row_collapsed)

        self.visible_docids = None

        self._all_cats = self.parse_applications_menu('/usr/share/app-install')
        self._all_cats = categories_sorted_by_name(self._all_cats)

        # initial build of installed tree
        self._build_categorised_view()

        # now we are initialized
        self.emit("installed-pane-created")
        self.show_all()
        self.view_initialized = True
        return False

    def _on_row_collapsed(self, view, it, path):
        return

    def _row_visibility_func(self, model, it, col):

        if self.visible_docids is None:

            row = model.get_value(it, col)
            if isinstance(row, CategoryRowReference):
                row.vis_count = row.pkg_count
            return True

        row = model.get_value(it, col)
        if isinstance(row, CategoryRowReference):
            visible = row.untranslated_name in self.visible_cats.keys()

            if visible:
                row.vis_count = self.visible_cats[row.untranslated_name]

            # process one event
            while Gtk.events_pending():
                Gtk.main_iteration()

            return visible

        if row is None: return False

        return row.get_docid() in self.visible_docids

    def _use_category(self, cat):
        # System cat is large and slow to search, filter it in default mode

        if 'carousel-only' in cat.flags or \
            ((self.nonapps_visible == NonAppVisibility.NEVER_VISIBLE) and \
            cat.untranslated_name == 'System'): return False

        return True

    #~ @interrupt_build_and_wait
    def _build_categorised_view(self):
        print 'Rebuilding categorised installedview...'
        self.cat_docid_map = {}
        model = self.base_model # base model not treefilter
        model.clear()

        i = 0

        print "NonAppVisibility", self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE
        
        for cat in self._all_cats:

            if not self._use_category(cat): continue
            self.enquirer.set_query(cat.query,
                                    sortmode=SortMethods.BY_ALPHABET,
                                    nonapps_visible=self.nonapps_visible,
                                    filter=self.state.filter,
                                    nonblocking_load=False,
                                    persistent_duplicate_filter=(i>0))

            L = len(self.enquirer.matches)
            if L:
                i += L
                docs = self.enquirer.get_documents()
                self.cat_docid_map[cat.untranslated_name] = [doc.get_docid() for doc in docs]

                model.set_category_documents(cat, docs)

                #~ self._check_expand()

                cursor_path = self.app_view.get_cursor()
                first = Gtk.TreePath.new_first()
                if cursor_path != first.get_indices():
                    self.app_view.set_cursor(first, None, False)

        # cache the installed app count
        self.installed_count = i
        self.emit("app-list-changed", i)
        return

    def _check_expand(self):
        it = self.treefilter.get_iter_first()
        while it:
            path = self.treefilter.get_path(it)
            if self.state.search_term:# or path in self._user_expanded_paths:
                self.app_view.expand_row(path, False)
            else:
                self.app_view.collapse_row(path)

            it = self.treefilter.iter_next(it)
        return

    def _search(self, terms=None):
        if not terms:
            self.visible_docids = self.state.search_term = None
            self._clear_search()
        elif self.state.search_term != terms:
            self.state.search_term = terms
            self.enquirer.set_query(self.get_query(),
                                    nonapps_visible=self.nonapps_visible,
                                    filter=self.apps_filter,
                                    nonblocking_load=True)

            self.visible_docids = self.enquirer.get_docids()
            self.visible_cats = self._get_vis_cats(self.visible_docids)

        self.treefilter.refilter()
        if terms:
            self.app_view.expand_all()
            i = len(self.visible_docids)
        else:
            self._check_expand()
            i = self.installed_count

        self.emit("app-list-changed", i)
        return

    def get_query(self):
        # search terms
        return self.db.get_query_list_from_search_entry(
                                        self.state.search_term)

    def update_show_hide_nonapps(self, length=-1):
        # override SoftwarePane.update_show_hide_nonapps
        """
        update the state of the show/hide non-applications control
        in the action_bar
        """
        #~ appstore = self.app_view.get_model()
        #~ if not appstore:
            #~ self.action_bar.unset_label()
            #~ return
        
        # first figure out if we are only showing installed
        enquirer = self.enquirer
        enquirer.filter = self.state.filter

        self.action_bar.unset_label()

        if self.nonapps_visible == NonAppVisibility.ALWAYS_VISIBLE:
            label = _("_Hide technical software_")
            self.action_bar.set_label(label, self._hide_nonapp_pkgs) 
        else:
            label = _("_Display technical software_")
            self.action_bar.set_label(label, self._show_nonapp_pkgs)
        return

    @wait_for_apt_cache_ready
    def refresh_apps(self, *args, **kwargs):
        """refresh the applist and update the navigation bar """
        logging.debug("installedpane refresh_apps")
        self._build_categorised_view()
        if self.state.search_term:
            self._search(self.state.search_term)
        return

    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear()

    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)

        self._search(terms.strip())

        self.notebook.set_current_page(InstalledPages.LIST)
        return

    def _get_vis_cats(self, visids):
        vis_cats = {}

        for cat_uname, docids in self.cat_docid_map.iteritems():
            children = len(set(docids) & set(visids))
            if children:
                vis_cats[cat_uname] = children

        return vis_cats

    def on_db_reopen(self, db):
        self.refresh_apps(rebuild=True)
        self.app_details_view.refresh_app()

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def get_callback_for_page(self, page, state):
        if page == InstalledPages.LIST:
            return self.display_overview_page
        return self.display_details_page

    def display_search(self):
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()
    
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == InstalledPages.APP_DETAILS:
            return ""
        # otherwise, show status based on search or not
        model = self.app_view.get_model()
        if not model:
            return ""
        if self.apps_search_term:
            if self.visible_docids is None: 
                return
            length = len(self.visible_docids)
            return gettext.ngettext("%(amount)s matching item",
                                    "%(amount)s matching items",
                                    length) % { 'amount' : length, }
        else:
            length = self.installed_count
            return gettext.ngettext("%(amount)s item installed",
                                    "%(amount)s items installed",
                                    length) % { 'amount' : length, }

    def display_overview_page(self, page, view_state):
        self.update_show_hide_nonapps()
        return True

    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False
        
    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == InstalledPages.LIST
        
    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == InstalledPages.APP_DETAILS

    def show_app(self, app):
        """ Display an application in the installed_pane """
        self.navigation_bar.remove_all(do_callback=False, animate=False) # do_callback and animate *must* both be false here
        details = app.get_details(self.db)
        self.navigation_bar.add_with_id(details.display_name,
                                        self.on_navigation_details,
                                        NavButtons.DETAILS,
                                        animate=False)
        self.app_details_view.show_app(app)
        self.app_view.emit("application-selected", app)

if __name__ == "__main__":

    from softwarecenter.paths import XAPIAN_BASE_PATH
    from softwarecenter.db.database import StoreDatabase

    #logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    Gtk.Window.set_default_icon_name("softwarecenter")

    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    # xapian
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    try:
        db = StoreDatabase(pathname, cache)
        db.open()
    except xapian.DatabaseOpeningError:
        # Couldn't use that folder as a database
        # This may be because we are in a bzr checkout and that
        #   folder is empty. If the folder is empty, and we can find the
        # script that does population, populate a database in it.
        if os.path.isdir(pathname) and not os.listdir(pathname):
            from softwarecenter.db.update import rebuild_database
            logging.info("building local database")
            rebuild_database(pathname)
            db = StoreDatabase(pathname, cache)
            db.open()
    except xapian.DatabaseCorruptError, e:
        logging.exception("xapian open failed")
        view.dialogs.error(None, 
                           _("Sorry, can not open the software database"),
                           _("Please re-install the 'software-center' "
                             "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)

    w = InstalledPane(cache, db, 'Ubuntu', icons, datadir)
    w.show()

    win = Gtk.Window()
    win.add(w)
    w.init_view()
    win.set_size_request(400, 600)
    win.show_all()
    win.connect("destroy", lambda x: Gtk.main_quit())

    Gtk.main()

