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
        self.app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
        self.app.window_main.show_all()
        self._p()

    def _run_search(self, search_text):
        logging.info("_run_search", search_text)
        self.app.available_pane.searchentry.delete_text(0, -1)
        self.app.available_pane.searchentry.insert_text(search_text)
        self._p()
        time.sleep(2)
        self._p()
        return self.app.available_pane.app_view.get_model()

    def assertFirstPkgInModel(self, model, needle):
        pkgname_from_row = model[0][AppStore.COL_PKGNAME]
        self.assertEqual(
            pkgname_from_row, needle, "expected row '%s' got '%s'" % (
                needle, pkgname_from_row))

    def test_unity_launcher_ui(self):
        # test package is the inimitable lincity-ng, the app with the
        # nicest little icon west of the pecos
        #
        # Note: this test relies on lincity-ng actually *not being installed*
        #       on the test machine!
        model = self._run_search("lincity-ng")
        self.assertFirstPkgInModel(model, "lincity-ng")
        treeview = self.app.available_pane.app_view
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        # click the "Install" button
        self.app.available_pane.app_details_view.pkg_statusbar.button.clicked()
        self._p()
        time.sleep(1)


if __name__ == "__main__":
    unittest.main()
