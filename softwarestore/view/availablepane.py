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

from widgets.navigationbar import NavigationBar
from widgets.searchentry import SearchEntry

from appview import AppView, AppStore, AppViewFilter
from catview import CategoriesView

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-store
       It contains a search entry and navigation buttons
    """

    DEFAULT_SEARCH_APPS_LIMIT = 200

    (PAGE_CATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(3)

    def __init__(self, cache, db, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, icons, datadir)
        # state
        self.apps_category_query = None
        self.apps_search_query = None
        self.apps_sorted = True
        self.apps_limit = 0
        self.apps_filter = AppViewFilter(cache)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self._status_text = ""
        self.connect("app-list-changed", self._on_app_list_changed)
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
        # categories, appview and details into the notebook in the bottom
        self.cat_view = CategoriesView(self.datadir, APP_INSTALL_PATH, 
                                       self.xapiandb,
                                       self.icons)
        scroll_categories = gtk.ScrolledWindow()
        scroll_categories.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_categories.add(self.cat_view)
        self.notebook.append_page(scroll_categories, gtk.Label("categories"))
        # app list
        self.cat_view.connect("category-selected", self.on_category_activated)
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
        self.notebook.append_page(self.scroll_app_list, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))
        # home button
        self.navigation_bar.add_with_id(_("Get Free Software"), 
                                        self.on_navigation_category,
                                        "category")
    @wait_for_apt_cache_ready
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        # build query
        if self.apps_category_query and self.apps_search_query:
            query = xapian.Query(xapian.Query.OP_AND, 
                                 self.apps_category_query,
                                 self.apps_search_query)
        elif self.apps_category_query:
            query = self.apps_category_query
        elif self.apps_search_query:
            query = self.apps_search_query
        else:
            query = None
        # create new model and attach it
        new_model = AppStore(self.cache,
                             self.xapiandb, 
                             self.icons, 
                             query, 
                             limit=self.apps_limit,
                             sort=self.apps_sorted,
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        self.emit("app-list-changed", len(new_model))
        return False

    def update_navigation_button(self):
        """Update the navigation button"""
        if self.apps_category_query:
            cat =  self.apps_category_query.name
            self.navigation_bar.add_with_id(cat, self.on_navigation_list, "list")
   
    # status text woo
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return ""
        return self._status_text
    
    def _on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text up-to-date by
           keeping track of the app-list-changed signals
        """
        if len(self.searchentry.get_text()) > 0:
            self._status_text = gettext.ngettext("%s matching item",
                                                 "%s matching items",
                                                 length) % length
        else:
            self._status_text = gettext.ngettext("%s item available",
                                                 "%s items available",
                                                 length) % length
     
    # callbacks
    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        logging.debug("on_entry_changed: %s" % new_text)

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in a any category
        if not self.apps_category_query and not new_text:
            self.navigation_bar.get_button_from_id("category").activate()

        # if the user searches in the category page, reset the specific
        # category query (to ensure all apps are searched)
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            self.apps_category_query = None

        # DTRT if the search is reseted
        if not new_text:
            self.apps_limit = 0
            self.apps_sorted = True
            self.apps_search_query = None
        else:
            self.apps_search_query = self.xapiandb.get_query_from_search_entry(new_text)
            self.apps_sorted = False
            self.apps_limit = self.DEFAULT_SEARCH_APPS_LIMIT
        self.update_navigation_button()
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
    def on_navigation_category(self, button):
        """callback when the navigation button with id 'category' is clicked"""
        if not button.get_active():
            return
        # yeah for special cases - as discussed on irc, mpt
        # wants this to behave differently *if* we are not
        # in a sub-category *and* there is a search going on
        if not self.apps_category_query and self.apps_search_query:
            self.on_navigation_list(button)
            return
        # clear the search
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_sorted = True
        self.apps_search_query = None
        # remove navigation bar elements
        self.navigation_bar.remove_id("list")
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_CATEGORY)
        # emit signal here to ensure to show count of all available items
        self.emit("app-list-changed", self.xapiandb.get_doccount())
        self.searchentry.show()
    def on_navigation_list(self, button):
        """callback when the navigation button with id 'list' is clicked"""
        if not button.get_active():
            return
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.emit("app-list-changed", len(self.app_view.get_model()))
        self.searchentry.show()
    def on_navigation_details(self, button):
        """callback when the navigation button with id 'details' is clicked"""
        if not button.get_active():
            return
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
    def on_category_activated(self, cat_view, name, query):
        #print cat_view, name, query
        # FIXME: integrate this at a lower level, e.g. by sending a 
        #        full Category class with the signal
        query.name = name
        self.apps_category_query = query
        # show new category
        self.update_navigation_button()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)

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

    w = AvailablePane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(500,400)
    win.show_all()

    gtk.main()

