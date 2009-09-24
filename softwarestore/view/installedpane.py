# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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
import glib
import gobject
import gtk
import logging
import os
import sys
import string
import xapian

from gettext import gettext as _

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

from widgets.pathbar2 import PathBar as NavigationBar
from widgets.searchentry import SearchEntry

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class InstalledPane(SoftwarePane):
    """Widget that represents the installed panel in software-store
       It contains a search entry and navigation buttons
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)

    def __init__(self, cache, db, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, icons, datadir)
        # state
        self.apps_filter = AppViewFilter(cache)
        self.apps_filter.set_installed_only(True)
        # UI
        self._build_ui()

    def _build_ui(self):
        # navigation bar and search on top in a hbox
        self.navigation_bar = NavigationBar()
        self.searchentry = SearchEntry()
        self.searchentry.connect("terms-changed", self.on_search_terms_changed)
        top_hbox = gtk.HBox()
        top_hbox.pack_start(self.navigation_bar, padding=self.PADDING)
        top_hbox.pack_start(self.searchentry, expand=False, padding=self.PADDING)
        self.pack_start(top_hbox, expand=False, padding=self.PADDING)
        # a notebook below
        self.notebook = gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        self.pack_start(self.notebook)
        # appview and details into the notebook in the bottom
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
        self.notebook.append_page(self.scroll_app_list, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))
        # initial refresh
        self.search_terms = ""
        self.refresh_apps()

    @wait_for_apt_cache_ready
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        if self.search_terms:
            query = self.xapiandb.get_query_from_search_entry(self.search_terms)
        else:
            query = None
        self.navigation_bar.add_with_id(_("Installed Software"), 
                                        self.on_navigation_list,
                                        "list",
                                        icon="computer")
        # get a new store and attach it to the view
        new_model = AppStore(self.cache,
                             self.xapiandb, 
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

        if terms != "":
            self.navigation_bar.remove_id("details")
            self.navigation_bar.remove_id("search")
            self.navigation_bar.add_with_id(
                "Search for: <i>%s</i>" % terms,
                self.on_navigation_search,
                "search")
        else:
            self.navigation_bar.remove_id("details")
            self.navigation_bar.remove_id("search")

        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)

    def on_application_activated(self, appview, name, pkgname):
        """callback when a app is clicked"""
        logging.debug("on_application_activated: '%s'" % name)
        self.navigation_bar.add_with_id(name,
                                       self.on_navigation_details,
                                       "details")
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.app_details.show_app(name, pkgname)

    def on_navigation_list(self, pathpart, pathbar):
        """callback when the navigation button with id 'list' is clicked"""
        if not pathbar.get_active_part():
            return
        # remove the details and clear the search
        self.searchentry.clear()
        pathbar.remove_id("details")
        pathbar.remove_id("search")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
        self.emit("app-list-changed", len(self.app_view.get_model()))

    def on_navigation_details(self, pathpart, pathbar):
        """callback when the navigation button with id 'details' is clicked"""
        if not pathbar.get_active_part():
            return
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()

    def on_navigation_search(self, pathpart, pathbar):
        pathbar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.emit("app-list-changed", len(self.app_view.get_model()))
        self.searchentry.show()
        return

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
            return gettext.ngettext("%s installed item",
                                    "%s installed items",
                                    length) % length

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-store"

    db = xapian.Database(pathname)
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    cache = apt.Cache(apt.progress.OpTextProgress())
    cache.ready = True

    w = InstalledPane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(400,600)
    win.show_all()

    gtk.main()

