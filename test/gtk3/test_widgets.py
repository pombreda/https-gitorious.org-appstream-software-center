#!/usr/bin/python

import glib
from gi.repository import Gtk
import mock
import os
import sys
import unittest

sys.path.insert(0,"../..")

from mock import Mock

from softwarecenter.ui.gtk3.widgets.stars import get_test_stars_window
from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
from softwarecenter.ui.gtk3.widgets.backforward import get_test_backforward_window
from softwarecenter.ui.gtk3.widgets.containers import get_test_container_window
from softwarecenter.ui.gtk3.widgets.description import get_test_description_window


class TestStars(unittest.TestCase):
    """ tests the stars widget """

    def test_stars(self):
        win = get_test_stars_window()
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()

    def test_actionbar(self):
        mock = Mock()
        actionbar = ActionBar()
        actionbar.add_button("id1", "label", mock)
        actionbar.add_button("id2", "label", mock)
        actionbar.remove_button("id2")
        actionbar.remove_button("id1")
        win = Gtk.Window()
        win.set_size_request(400, 400)
        win.add(actionbar)
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()

    def test_backforward(self):
        win = get_test_backforward_window()
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()

    def test_containers(self):
        win = get_test_container_window()
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()

    def test_description(self):
        win = get_test_description_window()
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
