
import apt
import logging
import gtk
import os
import xapian

from SimpleGtkbuilderApp import SimpleGtkbuilderApp

from view.appview import AppView, AppStore, AppViewInstalledFilter
from view.catview import CategoriesView
from view.viewswitcher import ViewSwitcher, ViewSwitcherList

from gettext import gettext as _

XAPIAN_BASE_PATH = "/var/cache/app-install"
APP_INSTALL_PATH = "/usr/share/app-install"
ICON_PATH = APP_INSTALL_PATH+"/icons/"

class AppCenter(SimpleGtkbuilderApp):
    
    (NOTEBOOK_PAGE_CATEGORIES,
     NOTEBOOK_PAGE_APPLIST,
     NOTEBOOK_PAGE_PENDING) = range(3)

    def __init__(self, datadir):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/MptCenter.ui")

        # xapian
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.xapiandb = xapian.Database(pathname)

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path(ICON_PATH)

        # view switcher
        self.view_switcher = ViewSwitcher()
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()
        self.view_switcher.connect("row-activated", self.view_switcher_activated)

        # categories
        self.cat_view = CategoriesView(APP_INSTALL_PATH, self.xapiandb, self.icons)
        self.scrolledwindow_categories.add(self.cat_view)
        self.cat_view.show()
        self.cat_view.connect("item-activated", self.category_activated)
        
        # apps
        empty_store = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.app_view = AppView(empty_store)
        self.scrolledwindow_applist.add(self.app_view)
        self.app_view.show()

        # search
        self.entry_search.connect("changed", self.on_entry_search_changed)
        
        # data 
        # FIXME: progress or thread
        self.cache = apt.Cache()
        self.installed_filter = AppViewInstalledFilter(self.cache)

        # state
        self.apps_category_query = None
        self.apps_filter = None
        self.apps_search_query = None
        self.apps_sorted = True
        self.apps_limit = 0

    def get_query_from_search_entry(self, search_term):
        """ get xapian.Query from a search term string """
        parser = xapian.QueryParser()
        query = parser.parse_query(search_term)
        return query

    def on_button_home_clicked(self, widget):
        logging.debug("on_button_home_clicked")
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_CATEGORIES)

    def on_entry_search_changed(self, widget):
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
        self.refresh_apps()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def on_button_search_entry_clear_clicked(self, widget):
        self.entry_search.set_text("")

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
                             filter=self.apps_filter)
        self.app_view.set_model(new_model)
        id = self.statusbar_main.get_context_id("items")
        self.statusbar_main.push(id, _("%s items available") % len(new_model))

    def view_switcher_activated(self, view_switcher, row, column):
        logging.debug("view_switcher_activated")
        model = view_switcher.get_model()
        action = model[row][ViewSwitcherList.COL_ACTION]
        if action == ViewSwitcherList.ACTION_ITEM_AVAILABLE:
            logging.debug("show available")
            self.apps_filter = None
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_INSTALLED:
            logging.debug("show installed")
            self.apps_filter = self.installed_filter.filter
            self.refresh_apps()
        elif action == ViewSwitcherList.ACTION_ITEM_PENDING:
            logging.debug("show pending")
        else:
            assert False, "Not reached"

    def category_activated(self, cat_view, path):
        (name, pixbuf, query) = cat_view.get_model()[path]
        self.apps_category_query = query
        self.refresh_apps()
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)
