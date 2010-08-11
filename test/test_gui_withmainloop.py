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

class TestGUIWithMainLoop(unittest.TestCase):

    def setUp(self):
        self.app = app
    
    def _trigger_channel_change(self):
        # go to first category
        cat = self.app.available_pane.cat_view.categories[0]
        self.app.available_pane.cat_view.emit("category-selected", cat)
        self._p()
        # go to first app
        column = self.app.available_pane.app_view.get_column(0)
        self.app.available_pane.app_view.row_activated((0,), column)
        # trigger channels changed signal
        self.app.backend.emit("channels-changed", True)
        self._p()
        # we just add boosl here and do the asserts in the test_ function,
        # otherwise unittest gets confused
        # make sure we stay on the same page
        self._on_the_right_page = (self.app.available_pane.notebook.get_current_page() == self.app.available_pane.PAGE_APP_DETAILS)
        # there was a bug that makes the actionbar appear in the details
        # view, make sure this does not happen again
        self._action_bar_hidden = (self.app.available_pane.action_bar.get_property("visible") == False)
        # done
        self.app.on_menuitem_close_activate(None)

    def test_jump_on_channel(self):
        glib.timeout_add_seconds(1, self._trigger_channel_change)
        gtk.main()
        self.assertTrue(self._on_the_right_page)
        self.assertTrue(self._action_bar_hidden)
    
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    unittest.main()
