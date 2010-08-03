#!/usr/bin/python

import apt
import glib
import gtk
import logging
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, "..")

from softwarecenter.app import SoftwareCenterApp
from softwarecenter.enums import XAPIAN_BASE_PATH
from softwarecenter.view.appview import AppStore
from softwarecenter.view.availablepane import AvailablePane
from softwarecenter.db.application import Application

from softwarecenter.backend import get_install_backend

class SCTestGUI(unittest.TestCase):
    
    def setUp(self):
        if os.getuid() == 0:
            subprocess.call(["dpkg", "-r", "hello"])
        apt.apt_pkg.config.set("Dir::log::history", "/tmp")
        #apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
        self.app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH)
        self.app.window_main.show_all()
        self._p()

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def test_categories(self):
        from softwarecenter.view.catview import get_category_by_name
        # find games, ensure its there and select it
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_CATEGORY)
        cat = get_category_by_name(self.app.available_pane.cat_view.categories,
                                   "Games")
        self.assertNotEqual(cat, None)
        self.app.available_pane.cat_view.emit("category-selected", cat)
        self._p()
        # we have a subcategory, ensure we really see it
        cat = get_category_by_name(self.app.available_pane.subcategories_view.categories,
                                   "Simulation")
        self.assertNotEqual(cat, None)
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_SUBCATEGORY)
        # click on the subcategory and ensure we get a list
        self.app.available_pane.subcategories_view.emit("category-selected", cat)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APPLIST)
        # now the details
        treeview = self.app.available_pane.app_view
        model = treeview.get_model()
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APP_DETAILS)
        # NOW test the back-foward
        self.app.available_pane.back_forward.emit("left-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APPLIST)
        self.app.available_pane.back_forward.emit("right-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APP_DETAILS)
        # and more back/forward
        for i in range(10):
            self.app.available_pane.back_forward.emit("left-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_CATEGORY)
        self.app.available_pane.back_forward.emit("right-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_SUBCATEGORY)

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

    def test_install(self):
        # assert we find the right package
        model = self._run_search("hello")
        treeview = self.app.available_pane.app_view
        self.assertFirstPkgInModel(model, "hello")
        treeview.row_activated(model.get_path(model.get_iter_root()),
                               treeview.get_column(0))
        self._p()
        self.assertEqual(
            self.app.available_pane.app_details.action_bar.button.get_label(),
            "Install")
        self._p()
        # install only when runnig as root, as we require polkit promtps
        # otherwise
        # FIXME: provide InstallBackendSimulate()
        if os.getuid() == 0:
            backend = get_install_backend()
            backend.connect("transaction-finished", 
                            self._on_transaction_finished)
            self._install_done = False
            # now simulate a click, the UI will block until the glib timeout 
            # from the previous line hits
            self.app.available_pane.app_details.action_bar.button.clicked()
            self._p()
            self.assertEqual(self.app.available_pane.app_details.action_bar.label.get_text(),
                             "Installing...")
            self.assertFalse(self.app.available_pane.app_details.action_bar.button.get_property("visible"))
            glib.timeout_add_seconds(2, self._test_for_progress)
            while not self._install_done:
                while gtk.events_pending():
                    gtk.main_iteration()
                time.sleep(0.1)
        self.app.available_pane.searchentry.delete_text(0, -1)
        
    def _test_for_progress(self):
        self.assertTrue(self.app.available_pane.app_details.action_bar.progress.get_property("visible"))
        return False

    def _on_transaction_finished(self, transaction, status):
        print "_on_transaction_finished", transaction, status
        self._install_done = True

if __name__ == "__main__":
    unittest.main()
