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
from softwarecenter.enums import ACTION_BUTTON_ADD_TO_LAUNCHER, TRANSACTION_TYPE_INSTALL
from softwarecenter.utils import convert_desktop_file_to_installed_location
from softwarecenter.ui.gtk.appview import AppStore

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
    
    def _zzz(self):
        for i in range(10):
            time.sleep(0.1)
            self._p()

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def setUp(self):
        self.s_c_app = s_c_app
        # monkey patch is_unity_running
        softwarecenter.utils.is_unity_running = lambda: True
        self.s_c_app.available_pane._send_dbus_signal_to_unity_launcher = Mock()

    def _reset_ui(self):
        self.s_c_app.available_pane.navigation_bar.remove_all(animate=False)
        self._p()
        time.sleep(0.5)
        self._p()

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

    def _navigate_to_pkgname_and_click_install(self, pkgname):
        self._reset_ui()
        self.s_c_app.show_available_packages([pkgname])
        self._p()
        appname = self.s_c_app.available_pane.app_details_view.app.appname
        # pretend we started a install
        self.s_c_app.backend.emit("transaction-started", pkgname, appname, "testid101", TRANSACTION_TYPE_INSTALL)
        # wait a wee bit
        self._zzz()
        
    def test_unity_launcher_stays_after_install_finished(self):
        pkgname = "gl-117"
        mock_result = Mock()
        mock_result.pkgname = pkgname
        mock_result.success = True
        # now pretend
        self._navigate_to_pkgname_and_click_install(pkgname)
        # pretend we are done
        self.s_c_app.backend.emit("transaction-finished", mock_result)
        # this is normally set in the transaction-finished call but our
        # app is not really installed so we need to mock it here
        self.s_c_app.available_pane.unity_launcher_items[pkgname].installed_desktop_file_path = "/some/path"
        # wait a wee bit
        self._zzz()
        # ensure we still have the button
        button = self.s_c_app.available_pane.action_bar.get_button(
            ACTION_BUTTON_ADD_TO_LAUNCHER)
        self.assertNotEqual(button, None)
        self.assertTrue(button.get_property("visible"))
        # ensure we haven't called the launcher prematurely
        self.assertFalse(self.s_c_app.available_pane._send_dbus_signal_to_unity_launcher.called)
        # now click it and ensure its added even though the transaction is over
        button.clicked()
        self._zzz()
        # ensure the button is gone
        button = self.s_c_app.available_pane.action_bar.get_button(
            ACTION_BUTTON_ADD_TO_LAUNCHER)
        self.assertEqual(button, None)
        self.assertTrue(self.s_c_app.available_pane._send_dbus_signal_to_unity_launcher.called)


    def test_unity_launcher_integration(self):
        pkgname = "lincity-ng"
        self._navigate_to_pkgname_and_click_install(pkgname)
        # verify that the panel is shown offering to add the app to the launcher
        self.assertTrue(
            self.s_c_app.available_pane.action_bar.get_property("visible"))
        button = self.s_c_app.available_pane.action_bar.get_button(
            ACTION_BUTTON_ADD_TO_LAUNCHER)
        self.assertTrue(button is not None)
        # click the button 
        button.clicked()

        # check that a correct UnityLauncherInfo object has been created and added to the queue
        self.assertTrue(pkgname in self.s_c_app.available_pane.unity_launcher_items)
        launcher_info = self.s_c_app.available_pane.unity_launcher_items.pop(pkgname)
        # check the UnityLauncherInfo values themselves
        self.assertEqual(launcher_info.name, "Lincity-ng")
        self.assertEqual(launcher_info.icon_name, "lincity-ng")
        self.assertTrue(launcher_info.icon_x > 20)
        self.assertTrue(launcher_info.icon_y > 20)
        self.assertEqual(launcher_info.icon_size, 84)
        self.assertEqual(launcher_info.app_install_desktop_file_path, "/usr/share/app-install/desktop/lincity-ng.desktop")
        self.assertEqual(launcher_info.trans_id, "testid101")
        # finally, make sure the the app has been removed from the launcher queue        
        self.assertFalse(pkgname in self.s_c_app.available_pane.unity_launcher_items)
        
    def test_desktop_file_path_conversion(self):
        # test 'normal' case
        app_install_desktop_path = "./data/app-install/desktop/deja-dup.desktop"
        installed_desktop_path = convert_desktop_file_to_installed_location(app_install_desktop_path)
        self.assertEqual(installed_desktop_path, "./data/applications/deja-dup.desktop")
        # test encoded subdirectory case, e.g. e.g. kde4_soundkonverter.desktop
        app_install_desktop_path = "./data/app-install/desktop/kde4__soundkonverter.desktop"
        installed_desktop_path = convert_desktop_file_to_installed_location(app_install_desktop_path)
        self.assertEqual(installed_desktop_path, "./data/applications/kde4/soundkonverter.desktop")
        # test the for-purchase case (uses "software-center-agent" as its appdetails.desktop_file value)
        # FIXME: this will only work if update-manager is installed
        app_install_desktop_path = "software-center-agent"
        installed_desktop_path = convert_desktop_file_to_installed_location(app_install_desktop_path,
                                                                            "update-manager")
        self.assertEqual(installed_desktop_path, "/usr/share/applications/update-manager.desktop")
        # test case where we don't have a value for app_install_desktop_path (e.g. for a local .deb
        # install, see bug LP: #768158)
        installed_desktop_path = convert_desktop_file_to_installed_location(None,
                                                                            "update-manager")
        # FIXME: this will only work if update-manager is installed
        self.assertEqual(installed_desktop_path, "/usr/share/applications/update-manager.desktop")
        

if __name__ == "__main__":
    unittest.main()
