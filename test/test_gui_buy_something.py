#!/usr/bin/python

import apt
import glib
import gtk
import logging
import sys
import time
import unittest

sys.path.insert(0, "..")

from softwarecenter.app import SoftwareCenterApp
from softwarecenter.enums import XAPIAN_BASE_PATH
from softwarecenter.view.appview import AppStore

class SCBuySomething(unittest.TestCase):
    
    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def setUp(self):
        apt.apt_pkg.config.set("Dir::log::history", "/tmp")
        apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
        self.app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH)
        self.app.window_main.show_all()
        self._p()

    def assertFirstPkgInModel(self, model, needle):
        pkgname_from_row = model[0][AppStore.COL_PKGNAME]
        self.assertEqual(
            pkgname_from_row, needle, "excpeted row '%s' got '%s'" % (
                needle, pkgname_from_row))

    def _run_search(self, search_text):
        logging.info("_run_search", search_text)
        self.app.available_pane.searchentry.delete_text(0, -1)
        self.app.available_pane.searchentry.insert_text(search_text)
        self._p()
        time.sleep(1)
        self._p()
        return self.app.available_pane.app_view.get_model()

    def test_buy_something_gui(self):
        # assert we find the right package
        model = self._run_search("hellox")
        treeview = self.app.available_pane.app_view
        self.assertFirstPkgInModel(model, "hellox")
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        self._p()
        self.assertEqual(
            self.app.available_pane.app_details.action_bar.button.get_label(),
            "Buy")
        self._p()
        # close the purchase dialog again after 1s
        glib.timeout_add_seconds(1, lambda: self.app.available_pane.app_details.purchase_dialog.response(gtk.RESPONSE_OK))
        # now simulate a click, the UI will block until the glib timeout 
        # from the previous line hits
        self.app.available_pane.app_details.action_bar.button.clicked()
        self._p()
        # done


if __name__ == "__main__":
    unittest.main()
