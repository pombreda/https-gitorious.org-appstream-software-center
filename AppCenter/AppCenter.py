
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

        # data
        self.cache = apt.Cache()
        self.installed_filter = AppViewInstalledFilter(self.cache)

        # state
        self.current_query = None

    def refresh_apps(self, query=None, filter=None, sorted=True):
        # check if we have a new query
        if not query:
            query = self.current_query
        else:
            self.current_query = query
        # get new TreeModel
        new_model = AppStore(self.xapiandb, 
                             self.icons, 
                             query, 
                             limit=0,
                             sort=sorted,
                             filter=filter)
        self.app_view.set_model(new_model)
        id = self.statusbar_main.get_context_id("items")
        self.statusbar_main.push(id, _("%s items available") % len(new_model))

    def view_switcher_activated(self, view_switcher, row, column):
        logging.debug("view_switcher_activated")
        model = view_switcher.get_model()
        action = model[row][ViewSwitcherList.COL_ACTION]
        if action == ViewSwitcherList.ACTION_ITEM_AVAILABLE:
            logging.debug("show available")
            self.refresh_apps (filter=None)
        elif action == ViewSwitcherList.ACTION_ITEM_INSTALLED:
            logging.debug("show installed")
            self.refresh_apps(filter=self.installed_filter.filter)
        elif action == ViewSwitcherList.ACTION_ITEM_PENDING:
            logging.debug("show pending")
        else:
            assert False, "Not reached"

    def category_activated(self, cat_view, path):
        (name, pixbuf, query) = cat_view.get_model()[path]
        self.refresh_apps(query=query)
        self.notebook_view.set_current_page(self.NOTEBOOK_PAGE_APPLIST)

    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)
