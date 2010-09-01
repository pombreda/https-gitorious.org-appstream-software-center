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
        # reset
        self.app.available_pane.on_navigation_category(None, None)
        self._p()
        # navigate to first app
        self._navigate_to_first_app()
        # trigger channels changed signal
        self.app.backend.emit("channels-changed", True)
        self._p()
        # we just add bools here and do the asserts in the test_ function,
        # otherwise unittest gets confused
        # make sure we stay on the same page
        self._on_the_right_page = (self.app.available_pane.notebook.get_current_page() == self.app.available_pane.PAGE_APP_DETAILS)
        # there was a bug that makes the actionbar appear in the details
        # view, make sure this does not happen again
        self._action_bar_hidden = (self.app.available_pane.action_bar.get_property("visible") == False)
        # done
        self.app.on_menuitem_close_activate(None)

    def test_action_bar_visible_in_details_on_channel_change(self):
        glib.timeout_add_seconds(1, self._trigger_channel_change)
        gtk.main()
        self.assertTrue(self._on_the_right_page)
        self.assertTrue(self._action_bar_hidden)

    def _trigger_test_channel_view(self, condition):
        # reset
        self.app.available_pane.on_navigation_category(None, None)
        self._p()
        # go to the second channel
        column = self.app.view_switcher.get_column(0)
        self.app.view_switcher.set_cursor((0,1), column)
        self._p()
        # activate first app
        column = self.app.channel_pane.app_view.get_column(0)
        self.app.channel_pane.app_view.row_activated((0,), column)
        self._p()
        # now simulate a the condition
        if condition == "channels-changed":
            self.app.backend.emit("channels-changed", True)
        elif condition == "db-reopen":
            self.app.db.emit("reopen")
        else:
            self.assertNotReached("unknown condition")
        self._p()
        # we just add bools here and do the asserts in the test_ function,
        # make sure we stay on the same page
        self._on_the_right_channel_view_page = (self.app.channel_pane.notebook.get_current_page() == self.app.channel_pane.PAGE_APP_DETAILS)
        # done
        self.app.on_menuitem_close_activate(None)

    def test_channel_view(self):
        glib.timeout_add_seconds(1, self._trigger_test_channel_view, "channels-changed")
        gtk.main()
        self.assertTrue(self._on_the_right_channel_view_page)

    def test_channel_view_on_db_reopen(self):
        glib.timeout_add_seconds(1, self._trigger_test_channel_view, "db-reopen")
        gtk.main()
        self.assertTrue(self._on_the_right_channel_view_page)

    def _navigate_to_first_app(self):
        # go to first category
        cat = self.app.available_pane.cat_view.categories[0]
        self.app.available_pane.cat_view.emit("category-selected", cat)
        self._p()
        # go to first app
        column = self.app.available_pane.app_view.get_column(0)
        self.app.available_pane.app_view.row_activated((0,), column)

    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "-v":
        from softwarecenter.log import root
        root.setLevel(level=logging.DEBUG)
    unittest.main()
