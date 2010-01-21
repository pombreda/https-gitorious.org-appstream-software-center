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

from gettext import gettext as _

from softwarecenter.enums import *

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class InstalledPane(SoftwarePane):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        # state
        self.apps_filter = AppViewFilter(db, cache)
        self.apps_filter.set_installed_only(True)
        self.app_view.connect("application-selected", 
                              self.on_application_selected)
        self.current_appview_selection = None
        # UI
        self._build_ui()
    def _build_ui(self):
        self.notebook.append_page(self.scroll_app_list, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))
        # initial refresh
        self.search_terms = ""
        self.refresh_apps()

    def _show_installed_overview(self):
        " helper that goes back to the overview page "
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()

    @wait_for_apt_cache_ready
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        if self.search_terms:
            query = self.db.get_query_list_from_search_entry(self.search_terms)
            self.navigation_bar.add_with_id(_("Search Results"),
                                            self.on_navigation_search, 
                                            "search")
        else:
            query = None
        self.navigation_bar.add_with_id(_("Installed Software"), 
                                        self.on_navigation_list,
                                        "list")
        # get a new store and attach it to the view
        new_model = AppStore(self.cache,
                             self.db, 
                             self.icons, 
                             query, 
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        self.emit("app-list-changed", len(new_model))
        return False
    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)
        self.search_terms = terms
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
    def on_db_reopen(self, db):
        self.refresh_apps()
        self._show_installed_overview()
    def on_navigation_search(self, button):
        logging.debug("on_navigation_search")
        pass
    def on_navigation_list(self, button):
        """callback when the navigation button with id 'list' is clicked"""
        if not button.get_active():
            return
        # remove the details and clear the search
        self.searchentry.clear()
        self.navigation_bar.remove_id("search")
        self._show_installed_overview()
        # only emit something if the model is there
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))

    def on_navigation_details(self, button):
        """callback when the navigation button with id 'details' is clicked"""
        if not button.get_active():
            return
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
    
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return ""
        # otherwise, show status based on search or not
        length = len(self.app_view.get_model())
        if len(self.searchentry.get_text()) > 0:
            return gettext.ngettext("%s matching item",
                                    "%s matching items",
                                    length) % length
        else:
            return gettext.ngettext("%s application installed",
                                    "%s applications installed",
                                    length) % length
                                    
    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        if self.is_search_in_progress():
            model = self.app_view.get_model()
            if len(model) > 0:
                return self.app_view.get_model().apps[0]
            else:
                return None
        else:
            return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    db = xapian.Database(pathname)
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    cache = apt.Cache(apt.progress.OpTextProgress())
    cache.ready = True

    w = InstalledPane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(400, 600)
    win.show_all()

    gtk.main()

