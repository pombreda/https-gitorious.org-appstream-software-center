
import gtk
import os
import xapian


from SimpleGtkbuilderApp import SimpleGtkbuilderApp

from view.appview import AppView, AppStore
from view.catview import CategoriesView
from view.viewswitcher import ViewSwitcher


XAPIAN_BASE_PATH = "/var/cache/app-install"
APP_INSTALL_PATH = "/usr/share/app-install"
ICON_PATH = APP_INSTALL_PATH+"/icons/"

class AppCenter(SimpleGtkbuilderApp):
    
    def __init__(self, datadir):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/MptCenter.ui")

        # xapian
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        db = xapian.Database(pathname)

        # additional icons come from app-install-data
        icons = gtk.icon_theme_get_default()
        icons.append_search_path(ICON_PATH)

        # view switcher
        self.view_switcher = ViewSwitcher()
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()

        # categories
        self.cat_view = CategoriesView(APP_INSTALL_PATH, db, icons)
        self.scrolledwindow_categories.add(self.cat_view)
        self.cat_view.show()
        
        # apps
        store = AppStore(db, icons)
        self.app_view = AppView(store)
        self.scrolledwindow_applist.add(self.app_view)
        self.app_view.show()

    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)
