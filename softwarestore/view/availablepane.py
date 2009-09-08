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

from navigationbar import NavigationBar
from searchentry import SearchEntry
from appview import AppView, AppStore, AppViewFilter
from appdetailsview import AppDetailsView
from catview import CategoriesView

class AvailablePane(gtk.VBox):
    """Widget that represents the available panel in software-store
       It contains a search entry and navigation buttons
    """


    PADDING = 6
    (PAGE_CATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(3)

    def __init__(self, cache, db, icons, datadir):
        gtk.VBox.__init__(self)
        self.cache = cache
        self.xapiandb = db
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.icons = icons
        self.datadir = datadir
        self.apps_filter = AppViewFilter(cache)
        self.apps_filter.set_not_installed_only(True)
        self._build_ui()
    def _build_ui(self):
        # navigation bar and search on top in a hbox
        self.navigation_bar = NavigationBar()
        self.searchentry = SearchEntry()
        self.searchentry.connect("terms-changed", self.on_search_terms_changed)
        top_hbox = gtk.HBox()
        top_hbox.pack_start(self.navigation_bar)
        top_hbox.pack_start(self.searchentry, expand=False)
        self.pack_start(top_hbox, expand=False, padding=self.PADDING)
        # a notebook below
        self.notebook = gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.pack_start(self.notebook, padding=self.PADDING)
        # categories, appview and details into the notebook in the bottom
        self.cat_view = CategoriesView(self.datadir, APP_INSTALL_PATH, 
                                       self.xapiandb,
                                       self.icons)
        scroll_categories = gtk.ScrolledWindow()
        scroll_categories.add(self.cat_view)
        self.notebook.append_page(scroll_categories, gtk.Label("categories"))
        # app list
        self.cat_view.connect("category-selected", self.on_category_activated)
        self.app_view = AppView()
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
        scroll_app_list = gtk.ScrolledWindow()
        scroll_app_list.add(self.app_view)
        self.notebook.append_page(scroll_app_list, gtk.Label("installed"))
        # details
        self.app_details = AppDetailsView(self.xapiandb, 
                                          self.icons, 
                                          self.cache, 
                                          self.datadir)
        scroll_details = gtk.ScrolledWindow()
        scroll_details.add(self.app_details)
        self.notebook.append_page(scroll_details, gtk.Label("details"))
        # initial refresh
        self.category_query = None
        self.search_terms = ""
        self.refresh_apps()
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        if self.search_terms:
            # FIXME: move this into generic code? 
            #        something like "build_query_from_search_terms()"
            query = self.xapian_parser.parse_query(self.search_terms, 
                                              xapian.QueryParser.FLAG_PARTIAL)
            self.navigation_bar.add_with_id(_("Search in Get Free Software"), 
                                           self.on_navigation_category,
                                           "category")
        else:
            self.navigation_bar.add_with_id(_("Get Free Software"), 
                                           self.on_navigation_category,
                                           "category")
            query = None
        # get a new store and attach it to the view
        new_model = AppStore(self.cache,
                             self.xapiandb, 
                             self.icons, 
                             query, 
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)
        self.search_terms = terms
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
    def on_application_activated(self, appview, name):
        """callback when a app is clicked"""
        logging.debug("on_application_activated: '%s'" % name)
        self.app_details.show_app(name)
        self.navigation_bar.add_with_id(name,
                                       self.on_navigation_details,
                                       "details")
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
    def on_navigation_category(self, button):
        """callback when the navigation button with id 'category' is clicked"""
        self.notebook.set_current_page(self.PAGE_CATEGORY)
        self.searchentry.show()
    def on_navigation_list(self, button):
        """callback when the navigation button with id 'list' is clicked"""
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
    def on_navigation_details(self, button):
        """callback when the navigation button with id 'details' is clicked"""
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
    def on_category_activated(self, cat_view, name, query):
        #print cat_view, name, query
        # FIXME: integrate this at a lower level, e.g. by sending a 
        #        full Category class with the signal
        query.name = name
        self.category_query = query
        # show new category
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
        # update navigation bar
        self.navigation_bar.add_with_id(name, 
                                        self.on_navigation_list, 
                                        "list")



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

    w = AvailablePane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(500,400)
    win.show_all()

    gtk.main()

