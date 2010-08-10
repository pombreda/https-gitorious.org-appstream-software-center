#!/usr/bin/python

import apt
import glib
import gtk
import logging
from mock import Mock
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
from softwarecenter.view.catview import get_category_by_name
from softwarecenter.backend import get_install_backend

# needed for the install test
if os.getuid() == 0:
    subprocess.call(["dpkg", "-r", "4g8"])

# we make app global as its relatively expensive to create
# and in setUp it would be created and destroyed for each
# test
apt.apt_pkg.config.set("Dir::log::history", "/tmp")
#apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
mock_options = Mock()
mock_options.enable_lp = False
mock_options.enable_buy = True
app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
app.window_main.show_all()

class SCTestGUI(unittest.TestCase):

    def setUp(self):
        self.app = app
        self._p()
    
    def test_supported_only(self):
        """ test if clicking on the "supported only" menuitems
            really makes the the amount of items smaller
        """
        self._reset_ui()
        items_all = self.app.label_status.get_text()
        self.app.menuitem_view_supported_only.activate()
        items_supported = self.app.label_status.get_text()
        self.assertNotEqual(items_all, items_supported)
        len_all = int(items_all.split()[0])
        len_supported = int(items_supported.split()[0])
        self.assertTrue(len_all > len_supported)

    def test_categories_and_back_forward(self):
        self._reset_ui()

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

    def test_select_featured_and_back_forward(self):
        self._reset_ui()

        app = Application("Cheese","cheese")
        self.app.available_pane.cat_view.emit("application-activated", app)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APP_DETAILS)
        self.app.available_pane.back_forward.emit("left-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_CATEGORY)
        self.app.available_pane.back_forward.emit("right-clicked", None)
        self._p()
        self.assertEqual(self.app.available_pane.notebook.get_current_page(),
                         AvailablePane.PAGE_APP_DETAILS)


    def test_install_the_4g8_package(self):
        self._reset_ui()

        # assert we find the right package
        model = self._run_search("4g8")
        treeview = self.app.available_pane.app_view
        self.assertFirstPkgInModel(model, "4g8")
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

    def test_show_unavailable(self):
        # make sure that certain UI elements are hidden when showing
        # packages that are not available
        self.app.show_available_packages(["i-dont-exit"])
        self._p()
        self.assertFalse(self.app.available_pane.app_details.screenshot.get_property("visible"))

    # helper stuff
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()
        # for debugging the steps
        #print "press [ENTER]"
        #sys.stdin.readline()
            
    def _reset_ui(self):
        self.app.available_pane.navigation_bar.remove_all(animate=False)
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

    def _test_for_progress(self):
        self.assertTrue(self.app.available_pane.app_details.action_bar.progress.get_property("visible"))
        return False

    def _on_transaction_finished(self, *args, **kwargs):
        print "_on_transaction_finished", args
        self._install_done = True

if __name__ == "__main__":
    unittest.main()
