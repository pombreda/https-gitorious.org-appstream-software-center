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
import logging
import glib
import gtk
import os
import xapian
import sys

from SimpleGtkbuilderApp import SimpleGtkbuilderApp

try:
    from softwarestore.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from softwarestore.enums import *

from view.appview import AppView, AppStore, AppViewFilter
from view.catview import CategoriesView, LabeledCategoriesView
from view.viewswitcher import ViewSwitcher, ViewSwitcherList
from view.appdetailsview import AppDetailsView
from view.pendingview import PendingView
from view.navigationbar import NavigationBar
from view.searchentry import SearchEntry

from apt.aptcache import AptCache

from gettext import gettext as _


class SoftwareStoreApp(SimpleGtkbuilderApp):
    
    (NOTEBOOK_PAGE_CATEGORIES,
     NOTEBOOK_PAGE_APPLIST,
     NOTEBOOK_PAGE_APP_DETAILS,
     NOTEBOOK_PAGE_PENDING) = range(4)

    DEFAULT_SEARCH_APPS_LIMIT = 200

    def __init__(self, datadir, package=None):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/SoftwareStore.ui")

        # xapian
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.xapiandb = xapian.Database(pathname)
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        #self.xapian_parser.add_boolean_prefix("section", "AS")

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path(ICON_PATH)

        # cursor
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
        
        # a main iteration friendly apt cache
        self.cache = AptCache()

        # navigation bar
        self.navigation_bar = NavigationBar(self.button_home)
        self.hbox_navigation_buttons.pack_start(self.navigation_bar)
        self.navigation_bar.show()

        # view switcher
        self.view_switcher = ViewSwitcher(self.icons)
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()
        self.view_switcher.set_cursor((0,))
        self.view_switcher.connect("row-activated", 
                                   self.on_view_switcher_activated)

        # categories
        self.cat_view = CategoriesView(APP_INSTALL_PATH, self.xapiandb,
                                       self.icons)
        self.scrolledwindow_categories.add(self.cat_view)
        self.cat_view.show()
        self.cat_view.connect("category-selected", self.on_category_activated)
        
        # apps
        empty_store = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.app_view = AppView(empty_store)
        self.app_view.connect("row-activated", self.on_app_activated)
        self.scrolledwindow_applist.add(self.app_view)
        self.app_view.show()

        # pending
        self.pending_view = PendingView(self.icons)
        self.scrolledwindow_transactions.add(self.pending_view)

        # details
        self.app_details_view = AppDetailsView(self.xapiandb, self.icons, self.cache)
        self.scrolledwindow_app_details.add(self.app_details_view)
        self.app_details_view.show()

        # search
        self.entry_search = SearchEntry(self.icons)
        self.hbox_search_entry.pack_start(self.entry_search)
        self.entry_search.connect("terms-changed", self.on_entry_search_changed)
        
        # if package is supplied on commandline
        if package:
            package = package[0].replace('apt:', '')
            
            try:
                self.app_details_view.show_app(package)
                self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APP_DETAILS)
                # add navigation button
                self.navigation_bar.add_with_id(package, self.on_navigation_button_app_details, "app")
            except IndexError:
                self.messagedialog(title="Error", primary=_("Package Not Found"), 
                    secondary=_("The package <b>%s</b> was not found." % package), dialogtype=gtk.MESSAGE_ERROR)
                sys.exit()
    
        # state
        self.apps_filter = AppViewFilter(self.cache)
        self.apps_category_query = None
        self.apps_search_query = None
        self.apps_sorted = True
        self.apps_limit = 0
        
        # launchpad integration help, its ok if that fails
        try:
            import LaunchpadIntegration
            LaunchpadIntegration.set_sourcepackagename("software-store")
            LaunchpadIntegration.add_items(self.menu_help, 1, True, False)
        except Exception, e:
            logging.debug("launchpad integration error: '%s'" % e)

        # default focus
        self.cat_view.grab_focus()

    # xapian query
    def get_query_from_search_entry(self, search_term):
        """ get xapian.Query from a search term string """
        query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL)
        # FIXME: expand to add "AA" and "AP" before each search term?
        return query

    # callbacks
    def on_menuitem_search_activate(self, widget):
        #print "on_menuitem_search_activate"
        self.entry_search.grab_focus()
        self.entry_search.select_region(0, -1)

    def on_menuitem_close_activate(self, widget):
        gtk.main_quit()

    def on_menuitem_about_activate(self, widget):
        #print "about"
        self.aboutdialog.run()
        self.aboutdialog.hide()

    def on_menuitem_view_all_activate(self, widget):
        #print "on_menuitem_view_all_activate", widget
        self.apps_filter.set_supported_only(False)
        self.refresh_apps()

    def on_menuitem_view_canonical_activate(self, widget):
        #print "on_menuitem_view_canonical_activate", widget
        self.apps_filter.set_supported_only(True)
        self.refresh_apps()

    def on_window_main_delete_event(self, widget, event):
        gtk.main_quit()

    def on_button_home_clicked(self, widget):
        logging.debug("on_button_home_clicked")
        # we get the clicked signal when the radio-group toggles
        # so we do not react unless we were not already pressed in
        if not widget.get_active():
            return
        self.apps_category_query = None
        self.navigation_bar.remove_all()
        self.on_button_search_entry_clear_clicked(None)
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)

    def on_entry_search_changed(self, widget, new_text):
        self.navigation_bar.remove_id("search")
        logging.debug("on_entry_changed: %s" % new_text)
        if not new_text:
            self.apps_limit = 0
            self.apps_sorted = True
            self.apps_search_query = None
        else:
            self.apps_search_query = self.get_query_from_search_entry(new_text)
            self.apps_sorted = False
            self.apps_limit = self.DEFAULT_SEARCH_APPS_LIMIT
            if self.apps_category_query:
                cat =  self.apps_category_query.name
            else:
                cat = _("All")
            self.navigation_bar.add_with_id(_("Search in %s") % cat, 
                                            self.on_navigation_button_category, 
                                            "category")
        self.refresh_apps()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def on_button_search_entry_clear_clicked(self, widget):
        self.entry_search.set_text("")

    def on_view_switcher_activated(self, view_switcher, row, column):
        logging.debug("view_switcher_activated")
        model = view_switcher.get_model()
        action = model[row][ViewSwitcherList.COL_ACTION]
        if action == ViewSwitcherList.ACTION_ITEM_AVAILABLE:
            logging.debug("show available")
            self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)
            self.navigation_bar.remove_all()
            self.apps_filter.set_installed_only(False)
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_INSTALLED:
            logging.debug("show installed")
            self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)
            self.apps_filter.set_installed_only(True)
            self.navigation_bar.remove_all()
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_PENDING:
            logging.debug("show pending")
            self.navigation_bar.remove_all()
            self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_PENDING)
        else:
            assert False, "Not reached"

    def on_navigation_button_category(self, widget):
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def on_navigation_button_app_details(self, widget):
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APP_DETAILS)

    def on_app_activated(self, app_view, path, column):
        (name, text, icon) = app_view.get_model()[path]
        # show new app
        self.app_details_view.show_app(name)
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APP_DETAILS)
        # add navigation button
        self.navigation_bar.add_with_id(name, 
                                        self.on_navigation_button_app_details, 
                                        "app")

    def on_category_activated(self, cat_view, name, query):
        #print cat_view, name, query
        self.apps_category_query = query
        # show new category
        self.refresh_apps()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)
        # update navigation bar
        self.navigation_bar.add_with_id(name, 
                                        self.on_navigation_button_category, 
                                        "category")

    # gui helper

    def refresh_apps(self):
        # wait if the cache is not ready yet
        if not self.cache.ready:
            self.window_main.window.set_cursor(self.busy_cursor)
            glib.timeout_add(100, lambda: self.refresh_apps())
            return False
        self.window_main.window.set_cursor(None)

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
        new_model = AppStore(self.xapiandb, 
                             self.icons, 
                             query, 
                             limit=self.apps_limit,
                             sort=self.apps_sorted,
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        id = self.statusbar_main.get_context_id("items")
        self.statusbar_main.push(id, _("%s items available") % len(new_model))

    def messagedialog(self, title, primary=None, secondary=None, dialogbuttons=gtk.BUTTONS_OK, dialogtype=gtk.MESSAGE_INFO):
        dialog = gtk.MessageDialog(parent=None, flags=0, type=dialogtype, buttons=dialogbuttons, message_format=primary)
        dialog.set_title(title)
        if secondary:
            dialog.format_secondary_markup(secondary)
        result = dialog.run()
        dialog.hide()
        return result
        

    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)
