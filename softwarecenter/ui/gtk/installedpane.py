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
import gtk
import logging
import os
import sys
import xapian
import gobject

from gettext import gettext as _

from softwarecenter.enums import *
from softwarecenter.utils import wait_for_apt_cache_ready

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane

class InstalledPane(SoftwarePane):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)
     
    __gsignals__ = {'installed-pane-created':(gobject.SIGNAL_RUN_FIRST,
                                              gobject.TYPE_NONE,
                                              ())}

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        # state
        self.apps_filter = AppViewFilter(db, cache)
        self.apps_filter.set_installed_only(True)
        self.current_appview_selection = None
        self.loaded = False
        self.pane_name = _("Installed Software")
        
    def init_view(self):
        if not self.view_initialized:
            SoftwarePane.init_view(self)
            self.navigation_bar.set_size_request(26, -1)
            self.notebook.append_page(self.box_app_list, gtk.Label("installed"))
            # details
            self.notebook.append_page(self.scroll_details, gtk.Label("details"))
            # initial refresh
            self.apps_search_term = ""
            # now we are initialized
            self.emit("installed-pane-created")
            self.show_all()
            self.view_initialized = True

    def _show_installed_overview(self):
        " helper that goes back to the overview page "
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
        
    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear()
        self.navigation_bar.remove_id(NAV_BUTTON_ID_SEARCH)

    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)
        self.apps_search_term = terms
        if not self.apps_search_term:
            self._clear_search()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
    def on_db_reopen(self, db):
        self.refresh_apps()
        self.app_details_view.refresh_app()
        
    def on_navigation_search(self, pathbar, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()
        
    def on_navigation_list(self, pathbar, part):
        """callback when the navigation button with id 'list' is clicked"""
        if not self.loaded:
            self.refresh_apps()
        if not pathbar.get_active():
            return
        self._clear_search()
        self._show_installed_overview()
        # only emit something if the model is there
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))

    def on_navigation_details(self, pathbar, part):
        """callback when the navigation button with id 'details' is clicked"""
        if not pathbar.get_active():
            return
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
        self.action_bar.clear()
        
    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app
        
    def display_search(self):
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()
    
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return ""
        # otherwise, show status based on search or not
        model = self.app_view.get_model()
        if not model:
            return ""
        length = len(model)
        if len(self.searchentry.get_text()) > 0:
            return gettext.ngettext("%(amount)s matching item",
                                    "%(amount)s matching items",
                                    length) % { 'amount' : length, }
        else:
            return gettext.ngettext("%(amount)s item installed",
                                    "%(amount)s items installed",
                                    length) % { 'amount' : length, }
                                    
    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False
        
    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == self.PAGE_APPLIST
        
    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == self.PAGE_APP_DETAILS

    def show_app(self, app):
        """ Display an application in the installed_pane """
        self.navigation_bar.add_with_id(self.pane_name, 
                                        self.on_navigation_list, 
                                        NAV_BUTTON_ID_LIST, 
                                        do_callback=False, 
                                        animate=False)
        self.navigation_bar.remove_all(do_callback=False, animate=False) # do_callback and animate *must* both be false here
        details = app.get_details(self.db)
        self.navigation_bar.add_with_id(details.display_name,
                                        self.on_navigation_details,
                                        NAV_BUTTON_ID_DETAILS,
                                        animate=False)
        self.app_details_view.show_app(app)
        self.app_view.emit("application-selected", app)

if __name__ == "__main__":

    from softwarecenter.db.database import StoreDatabase

    #logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir,"icons"))
    icons.append_search_path(os.path.join(datadir,"emblems"))
    # HACK: make it more friendly for local installs (for mpt)
    icons.append_search_path(datadir+"/icons/32x32/status")
    gtk.window_set_default_icon_name("softwarecenter")
    cache = apt.Cache(apt.progress.text.OpProgress())
    cache.ready = True

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

    win = gtk.Window()
    win.add(w)
    w.init_view()
    win.set_size_request(400, 600)
    win.show_all()

    gtk.main()

