#!/usr/bin/python

import apt
import gtk
import logging
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0, "..")

from softwarecenter.app import SoftwareCenterApp
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.view.appview import AppStore
from softwarecenter.db.application import Application

# see https://wiki.ubuntu.com/SoftwareCenter#Learning%20how%20to%20launch%20an%20application

class TestUnityLauncherIntegration(unittest.TestCase):
    
    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def setUp(self):
        # options
        mock_options = Mock()
        mock_options.enable_lp = False
        mock_options.enable_buy = True
        apt.apt_pkg.config.set("Dir::log::history", "/tmp")
        apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
        self.s_c_app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
        self.s_c_app.window_main.show_all()
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

    def test_unity_launcher_integration(self):
        # test package is the inimitable lincity-ng
        # Note: this test relies on lincity-ng actually *not being installed*
        #       on the test machine!
        model = self._run_search("lincity-ng")
        self.assertFirstPkgInModel(model, "lincity-ng")
        treeview = self.s_c_app.available_pane.app_view
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        # click the "Install" button
        self.s_c_app.available_pane.app_details_view.pkg_statusbar.button.clicked()
        self._p()
        time.sleep(4)
        
        # now test the values to be used in the dbus call
        app = Application("", model[0][AppStore.COL_PKGNAME])
        (icon_name,
        icon_file_path,
        icon_size,
        icon_x,
        icon_y) = self.s_c_app.available_pane._get_icon_details_for_launcher_service(app)
        print "values for use in the unity launcher dbus call:"
        # print "   (icon_name): ", icon_name
        print "   app.name: ", app.name
        print "   icon_file_path: ", icon_file_path
        print "   icon_x: ", icon_x
        print "   icon_y: ", icon_y
        print "   icon_size: ", icon_size
#        print "   appdetails.desktop_file: ", appdetails.desktop_file
#        print "   trans_id: ", trans_id


if __name__ == "__main__":
    unittest.main()
