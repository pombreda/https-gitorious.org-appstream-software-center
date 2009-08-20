
import apt
import logging
import gtk
import os
import xapian

from SimpleGtkbuilderApp import SimpleGtkbuilderApp

from view.appview import AppView, AppStore, AppViewAptFilter
from view.catview import CategoriesView
from view.viewswitcher import ViewSwitcher, ViewSwitcherList
from view.appdetailsview import AppDetailsView
from view.pendingview import PendingView

from gettext import gettext as _

XAPIAN_BASE_PATH = "/var/cache/app-install"
APP_INSTALL_PATH = "/usr/share/app-install"
ICON_PATH = APP_INSTALL_PATH+"/icons/"

class AppCenter(SimpleGtkbuilderApp):
    
    (NOTEBOOK_PAGE_CATEGORIES,
     NOTEBOOK_PAGE_APPLIST,
     NOTEBOOK_PAGE_APP_DETAILS,
     NOTEBOOK_PAGE_PENDING) = range(4)

    def __init__(self, datadir):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/AppCenter.ui")

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

        # data 
        # FIXME: progress or thread
        self.cache = apt.Cache()

        # view switcher
        self.view_switcher = ViewSwitcher()
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()
        self.view_switcher.connect("row-activated", 
                                   self.on_view_switcher_activated)

        # categories
        self.cat_view = CategoriesView(APP_INSTALL_PATH, self.xapiandb, self.icons)
        self.scrolledwindow_categories.add(self.cat_view)
        self.cat_view.show()
        self.cat_view.connect("item-activated", self.on_category_activated)
        
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
        self.entry_search.connect("changed", self.on_entry_search_changed)

        # state
        self.apps_apt_filter = AppViewAptFilter(self.cache)
        self.apps_category_query = None
        self.apps_search_query = None
        self.apps_sorted = True
        self.apps_limit = 0

        # default focus
        self.entry_search.grab_focus()

    # xapian query
    def get_query_from_search_entry(self, search_term):
        """ get xapian.Query from a search term string """
        query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL)
        # FIXME: expand to add "AA" and "AP" before each search term?
        return query

    # navigation buttons
    def add_navigation_button(self, name, callback, type):
        self.remove_navigation_button(type)
        button = gtk.Button()
        button.set_label(name)
        button.show()
        button.connect("clicked", callback)
        button.set_data("navigation-type", type)
        self.hbox_navigation_buttons.pack_start(button, expand=False)

    def remove_navigation_buttons(self):
        for w in self.hbox_navigation_buttons:
            self.hbox_navigation_buttons.remove(w)

    def remove_navigation_button(self, type):
        for w in self.hbox_navigation_buttons:
            if w.get_data("navigation-type") == type:
                self.hbox_navigation_buttons.remove(w)

    # callbacks
    def on_menuitem_view_all_activate(self, widget):
        print "on_menuitem_view_all_activate", widget
        self.apps_apt_filter.set_supported_only(False)
        self.refresh_apps()

    def on_menuitem_view_canonical_activate(self, widget):
        print "on_menuitem_view_canonical_activate", widget
        self.apps_apt_filter.set_supported_only(True)
        self.refresh_apps()

    def on_button_home_clicked(self, widget):
        logging.debug("on_button_home_clicked")
        self.apps_category_query = None
        self.remove_navigation_buttons()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)

    def on_entry_search_changed(self, widget):
        self.remove_navigation_button("search")
        new_text = widget.get_text()
        logging.debug("on_entry_changed: %s" % new_text)
        if not new_text:
            self.apps_limit = 0
            self.apps_sorted = True
            self.apps_search_query = None
        else:
            self.apps_search_query = self.get_query_from_search_entry(new_text)
            self.apps_sorted = False
            self.apps_limit = 200
            self.add_navigation_button(_("Search"), 
                                       self.on_navigation_button_category, 
                                       "search")
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
            self.apps_apt_filter.set_installed_only(False)
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_INSTALLED:
            logging.debug("show installed")
            self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)
            self.apps_apt_filter.set_installed_only(True)
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_PENDING:
            logging.debug("show pending")
            self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_PENDING)
        else:
            assert False, "Not reached"

    def on_navigation_button_category(self, widget):
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def on_navigation_button_app_details(self, widget):
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APP_DETAILS)

    def on_app_activated(self, app_view, path, column):
        (name, icon) = app_view.get_model()[path]
        # show new app
        self.app_details_view.show_app(name)
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APP_DETAILS)
        # add navigation button
        self.add_navigation_button(name, self.on_navigation_button_app_details, "app")

    def on_category_activated(self, cat_view, path):
        (name, pixbuf, query) = cat_view.get_model()[path]
        self.apps_category_query = query
        # show new category
        self.refresh_apps()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)
        # update navigation bar
        self.add_navigation_button(name, self.on_navigation_button_category, "category")

    # gui helper
    def refresh_apps(self):
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
                             filter=self.apps_apt_filter)
        self.app_view.set_model(new_model)
        id = self.statusbar_main.get_context_id("items")
        self.statusbar_main.push(id, _("%s items available") % len(new_model))


    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)
