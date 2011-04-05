#!/usr/bin/python

import apt
import gtk
import logging
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0, "..")

import softwarecenter.utils
from softwarecenter.app import SoftwareCenterApp
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.enums import ACTION_BUTTON_ADD_TO_LAUNCHER
from softwarecenter.utils import convert_desktop_file_to_installed_location
from softwarecenter.view.appview import AppStore
from softwarecenter.db.application import Application

# see https://wiki.ubuntu.com/SoftwareCenter#Learning%20how%20to%20launch%20an%20application

# we make s_c_app global as its relatively expensive to create
# and in setUp it would be created and destroyed for each
# test
apt.apt_pkg.config.set("Dir::log::history", "/tmp")
#apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
mock_options = Mock()
mock_options.enable_lp = False
mock_options.enable_buy = True
s_c_app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
s_c_app.window_main.show_all()

class TestUnityLauncherIntegration(unittest.TestCase):
    
    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def setUp(self):
        self.s_c_app = s_c_app

    def _run_search(self, search_text):
        logging.info("_run_search", search_text)
        self.s_c_app.available_pane.searchentry.delete_text(0, -1)
        self.s_c_app.available_pane.searchentry.insert_text(search_text)
        self._p()
        time.sleep(2)
        self._p()
        return self.s_c_app.available_pane.app_view.get_model()

    def assertFirstPkgInModel(self, model, needle):
        pkgname_from_row = model[0][AppStore.COL_PKGNAME]
        self.assertEqual(
            pkgname_from_row, needle, "expected row '%s' got '%s'" % (
                needle, pkgname_from_row))

    def test_unity_launcher_integration(self):
        # monkey patch is_unity_running
        softwarecenter.utils.is_unity_running = lambda: True
        # test package is the inimitable lincity-ng
        # Note: this test relies on lincity-ng being *not installed*
        #       on the test machine!
        model = self._run_search("lincity-ng")
        self.assertFirstPkgInModel(model, "lincity-ng")
        treeview = self.s_c_app.available_pane.app_view
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        self._p()
        # click the "Install" button
        self.s_c_app.available_pane.app_details_view.pkg_statusbar.button.clicked()
        for i in range(2):
            self._p()
            time.sleep(0.3)
        
        
        # verify that the panel is shown offering to add the app to the launcher
        self.assertTrue(
            self.s_c_app.available_pane.action_bar.get_property("visible"))
        button = self.s_c_app.available_pane.action_bar.get_button(
            ACTION_BUTTON_ADD_TO_LAUNCHER)
        self.assertTrue(button is not None)
        
        # now test the values to be used in the dbus call
        app = Application("", model[0][AppStore.COL_PKGNAME])
        (icon_size, icon_x, icon_y) = self.s_c_app.available_pane._get_onscreen_icon_details_for_launcher_service(app)
        appdetails = app.get_details(self.s_c_app.db)
        trans_id = "/org/debian/apt/transaction/test101"
        # check that a correct UnityLauncherInfo object has been created and added to the queue
        self.s_c_app.available_pane.on_add_to_launcher(app, appdetails, trans_id)
        self.assertTrue(app.pkgname in self.s_c_app.available_pane.unity_launcher_items)
        launcher_info = self.s_c_app.available_pane.unity_launcher_items.pop(app.pkgname)
        # check the UnityLauncherInfo values themselves
        self.assertEqual(launcher_info.name, "Lincity-ng")
        self.assertEqual(launcher_info.icon_name, "lincity-ng")
        self.assertTrue(launcher_info.icon_x > 20)
        self.assertTrue(launcher_info.icon_y > 20)
        self.assertEqual(launcher_info.icon_size, 84)
        self.assertEqual(launcher_info.app_install_desktop_file_path, "/usr/share/app-install/desktop/lincity-ng.desktop")
        self.assertEqual(launcher_info.trans_id, "/org/debian/apt/transaction/test101")
        # finally, make sure the the app has been removed from the launcher queue        
        self.assertTrue(app.pkgname not in self.s_c_app.available_pane.unity_launcher_items)
        
    def test_desktop_file_path_conversion(self):
        import os.path
        # test 'normal' case
        app_install_desktop_path = "./data/app-install/desktop/deja-dup.desktop"
        installed_desktop_path = convert_desktop_file_to_installed_location(app_install_desktop_path)
        self.assertEqual(installed_desktop_path, "./data/applications/deja-dup.desktop")
        # test encoded subdirectory case, e.g. e.g. kde4_soundkonverter.desktop
        app_install_desktop_path = "./data/app-install/desktop/kde4__soundkonverter.desktop"
        installed_desktop_path = convert_desktop_file_to_installed_location(app_install_desktop_path)
        self.assertEqual(installed_desktop_path, "./data/applications/kde4/soundkonverter.desktop")
        

if __name__ == "__main__":
    unittest.main()
