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
from softwarecenter.utils import *

from appview import AppView, AppStore, AppViewFilter
from catview import CategoriesView

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    DEFAULT_SEARCH_APPS_LIMIT = 200

    (PAGE_CATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(3)
     
    __gsignals__ = {
        "category-view-selected" : (gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    ()
                                   )
        }

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir)
        # state
        self.apps_category = None
        self.apps_subcategory = None
        self.apps_search_query = None
        self.apps_sorted = True
        self.apps_limit = 0
        self.apps_filter = AppViewFilter(db, cache)
        self.apps_filter.set_only_packages_without_applications(True)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self._status_text = ""
        self.connect("app-list-changed", self._on_app_list_changed)
        # UI
        self._build_ui()
    def _build_ui(self):
        # categories, appview and details into the notebook in the bottom
        self.cat_view = CategoriesView(self.datadir, APP_INSTALL_PATH, 
                                       self.db,
                                       self.icons)
        scroll_categories = gtk.ScrolledWindow()
        scroll_categories.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_categories.add(self.cat_view)
        self.notebook.append_page(scroll_categories, gtk.Label("categories"))
        # sub-categories view
        self.subcategories_view = CategoriesView(self.datadir, 
                                                 APP_INSTALL_PATH, 
                                                 self.db,
                                                 self.icons,
                                                 self.cat_view.categories[0])
        self.subcategories_view.connect(
            "category-selected", self.on_subcategory_activated)
        self.scroll_subcategories = gtk.ScrolledWindow()
        self.scroll_subcategories.set_policy(
            gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll_subcategories.add(self.subcategories_view)
        # now a vbox for subcategories and applist 
        apps_vbox = gtk.VPaned()
        apps_vbox.pack1(self.scroll_subcategories, resize=True)
        apps_vbox.pack2(self.scroll_app_list)
        # app list
        self.cat_view.connect("category-selected", self.on_category_activated)
        self.notebook.append_page(apps_vbox, gtk.Label("installed"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))
        # home button
        self.navigation_bar.add_with_id(_("Get Free Software"), 
                                        self.on_navigation_category,
                                        "category")
    def _get_query(self):
        """helper that gets the query for the current category/search mode"""
        query = None
        # if we have a subquery, that one wins
        if self.apps_category and self.apps_subcategory:
            query = self.apps_subcategory.query
        elif self.apps_category:
            query = self.apps_category.query
        # build search query
        if self.apps_category and self.apps_search_query:
            query = xapian.Query(xapian.Query.OP_AND, 
                                 query,
                                 self.apps_search_query)
        elif self.apps_search_query:
            query = self.apps_search_query
        return query

    def _show_hide_subcategories(self):
        # check if have subcategories and are not in a subcategory
        # view - if so, show it
        if (self.apps_category and 
            self.apps_category.subcategories and
            not self.apps_subcategory):
            self.subcategories_view.set_subcategory(self.apps_category)
            self.scroll_subcategories.show()
        else:
            self.scroll_subcategories.hide()

    def _show_hide_applist(self):
        # now check if the apps_category view has entries and if
        # not hide it
        if (len(self.app_view.get_model()) ==0 and 
            self.apps_category and
            self.apps_category.subcategories and 
            not self.apps_subcategory):
            self.scroll_app_list.hide()
        else:
            self.scroll_app_list.show()

    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        self._show_hide_subcategories()
        self._refresh_apps_with_apt_cache()

    @wait_for_apt_cache_ready
    def _refresh_apps_with_apt_cache(self):
        # build query
        query = self._get_query()
        # create new model and attach it
        new_model = AppStore(self.cache,
                             self.db, 
                             self.icons, 
                             query, 
                             limit=self.apps_limit,
                             sort=self.apps_sorted,
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        # check if we show subcategoriy
        self._show_hide_applist()
        self.emit("app-list-changed", len(new_model))
        return False

    def update_navigation_button(self):
        """Update the navigation button"""
        if self.apps_category:
            cat =  self.apps_category.name
            self.navigation_bar.add_with_id(
                cat, self.on_navigation_list, "list")
   
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
            self._status_text = gettext.ngettext("%s application available",
                                                 "%s applications available",
                                                 length) % length

    def _show_category_overview(self):
        " helper that shows the category overview "
        # reset category query
        self.apps_category = None
        self.apps_subcategory = None
        # remove pathbar stuff
        self.navigation_bar.remove_id("list")
        self.navigation_bar.remove_id("sublist")
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_CATEGORY)
        self.emit("app-list-changed", len(self.db))
        self.searchentry.show()
     
    # callbacks
    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        logging.debug("on_entry_changed: %s" % new_text)

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in a any category
        if not self.apps_category and not new_text:
            # category activate will clear search etc
            self.navigation_bar.get_button_from_id("category").activate()
            return

        # if the user searches in the "all categories" page, reset the specific
        # category query (to ensure all apps are searched)
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            self.apps_category = None
            self.apps_subcategory = None

        # DTRT if the search is reseted
        if not new_text:
            self.apps_limit = 0
            self.apps_sorted = True
            self.apps_search_query = None
        else:
            self.apps_search_query = self.db.get_query_from_search_entry(new_text)
            self.apps_sorted = False
            self.apps_limit = self.DEFAULT_SEARCH_APPS_LIMIT
        self.update_navigation_button()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
    def on_db_reopen(self, db):
        " called when the database is reopened"
        self.refresh_apps()
        self._show_category_overview()
    def on_navigation_category(self, button):
        """callback when the navigation button with id 'category' is clicked"""
        if not button.get_active():
            return
        # yeah for special cases - as discussed on irc, mpt
        # wants this to behave differently *if* we are not
        # in a sub-category *and* there is a search going on
        if not self.apps_category and self.searchentry.get_text():
            self.on_navigation_list(button)
            return
        # clear the search
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_sorted = True
        self.apps_search_query = None
        self.emit("category-view-selected")
        self._show_category_overview()
    def on_navigation_list(self, button):
        """callback when the navigation button with id 'list' is clicked"""
        if not button.get_active():
            return
        self.navigation_bar.remove_id("sublist")
        self.navigation_bar.remove_id("details")
        if self.apps_subcategory:
            self.apps_subcategory = None
            self._set_category(self.apps_category)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.emit("app-list-changed", len(self.app_view.get_model()))
        self.searchentry.show()
    def on_navigation_list_subcategory(self, button):
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

    def on_subcategory_activated(self, cat_view, category):
        #print cat_view, name, query
        logging.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.apps_subcategory = category
        self._set_category(category)
        self.navigation_bar.add_with_id(
            category.name, self.on_navigation_list_subcategory, "sublist")

    def on_category_activated(self, cat_view, category):
        #print cat_view, name, query
        logging.debug("on_category_activated: %s %s" % (
                category.name, category))
        self.apps_category = category
        self._set_category(category)

    def _set_category(self, category):
        query = category.query
        query.name = category.name
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
        datadir = "/usr/share/software-center"

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

