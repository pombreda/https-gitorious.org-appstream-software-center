#!/usr/bin/python

from gi.repository import Gtk
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

# overwrite early
import softwarecenter.paths
import softwarecenter.utils
softwarecenter.paths.datadir = "../data"

from softwarecenter.enums import ActionButtons, TransactionTypes
from softwarecenter.utils import convert_desktop_file_to_installed_location
from softwarecenter.db.application import Application
from softwarecenter.ui.gtk3.panes.availablepane import get_test_window

# we can only have one instance of availablepane, so create it here
win = get_test_window()
available_pane = win.get_data("pane")

# see https://wiki.ubuntu.com/SoftwareCenter#Learning%20how%20to%20launch%20an%20application

class TestUnityLauncherIntegration(unittest.TestCase):
    
    def _zzz(self):
        for i in range(10):
            time.sleep(0.1)
            self._p()

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()

    def setUp(self):
        # monkey patch is_unity_running
        softwarecenter.utils.is_unity_running = lambda: True

    def _navigate_to_appdetails_and_install(self, pkgname):
        app = Application("", pkgname)
        available_pane.app_view.emit("application-activated",
                                     app)
        self._p()
        
        # pretend we started an install
        available_pane.backend.emit("transaction-started",
                                    app.pkgname, app.appname,
                                    "testid101",
                                    TransactionTypes.INSTALL)
        # wait a wee bit
        self._zzz()
        
    def test_unity_launcher_stays_after_install_finished(self):
        test_pkgname = "gl-117"
        mock_result = Mock()
        mock_result.pkgname = test_pkgname
        mock_result.success = True
        # now pretend
        # now pretend
        self._navigate_to_appdetails_and_install(test_pkgname)
        # pretend we are done
        available_pane.backend.emit("transaction-finished", mock_result)
        # this is normally set in the transaction-finished call but our
        # app is not really installed so we need to mock it here
        available_pane.unity_launcher_items[test_pkgname].installed_desktop_file_path = "/some/path"
        # wait a wee bit
        self._zzz()
        # ensure we still have the button
        button = available_pane.action_bar.get_button(
                ActionButtons.ADD_TO_LAUNCHER)
        self.assertNotEqual(button, None)
        self.assertTrue(button.get_property("visible"))
        # now click it even though the transaction is over
        button.clicked()
        self._zzz()
        # ensure the add to launcher button is now hidden
        button = available_pane.action_bar.get_button(
                ActionButtons.ADD_TO_LAUNCHER)
        self.assertEqual(button, None)

    def test_unity_launcher_integration(self):
        test_pkgname = "lincity-ng"
        mock_result = Mock()
        mock_result.pkgname = test_pkgname
        mock_result.success = True
        # now pretend
        self._navigate_to_appdetails_and_install(test_pkgname)
        
        # verify that the panel is shown offering to add the app to the launcher
        self.assertTrue(available_pane.action_bar.get_property("visible"))
        button = available_pane.action_bar.get_button(
            ActionButtons.ADD_TO_LAUNCHER)
        self.assertTrue(button is not None)
        # click the button 
        button.clicked()

        # check that a correct UnityLauncherInfo object has been created and
        # added to the queue
        self.assertTrue(test_pkgname in available_pane.unity_launcher_items)
        launcher_info = available_pane.unity_launcher_items.pop(test_pkgname)
        # check the UnityLauncherInfo values themselves
        self.assertEqual(launcher_info.name, "lincity-ng")
        self.assertEqual(launcher_info.icon_name, "lincity-ng")
        self.assertTrue(launcher_info.icon_x > 5)
        self.assertTrue(launcher_info.icon_y > 5)
        self.assertEqual(launcher_info.icon_size, 96)
        self.assertEqual(launcher_info.app_install_desktop_file_path,
            "/usr/share/app-install/desktop/lincity-ng:lincity-ng.desktop")
        self.assertEqual(launcher_info.trans_id, "testid101")
        # finally, make sure the the app has been removed from the launcher
        # queue        
        self.assertFalse(test_pkgname in available_pane.unity_launcher_items)
        
    def test_desktop_file_path_conversion(self):
        # test 'normal' case
        app_install_desktop_path = ("./data/app-install/desktop/" +
                                    "deja-dup:deja-dup.desktop")
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "deja-dup")
        self.assertEqual(installed_desktop_path,
                         "./data/applications/deja-dup.desktop")
        # test encoded subdirectory case, e.g. e.g. kde4_soundkonverter.desktop
        app_install_desktop_path = ("./data/app-install/desktop/" +
                                    "soundkonverter:" +
                                    "kde4__soundkonverter.desktop")
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "soundkonverter")
        self.assertEqual(installed_desktop_path,
                         "./data/applications/kde4/soundkonverter.desktop")
        # test the for-purchase case (uses "software-center-agent" as its
        # appdetails.desktop_file value)
        # FIXME: this will only work if update-manager is installed
        app_install_desktop_path = "software-center-agent"
        installed_desktop_path = convert_desktop_file_to_installed_location(
                app_install_desktop_path, "update-manager")
        self.assertEqual(installed_desktop_path,
                         "/usr/share/applications/update-manager.desktop")
        # test case where we don't have a value for app_install_desktop_path
        # (e.g. for a local .deb install, see bug LP: #768158)
        installed_desktop_path = convert_desktop_file_to_installed_location(
                None, "update-manager")
        # FIXME: this will only work if update-manager is installed
        self.assertEqual(installed_desktop_path,
                         "/usr/share/applications/update-manager.desktop")
        

if __name__ == "__main__":
    unittest.main()
