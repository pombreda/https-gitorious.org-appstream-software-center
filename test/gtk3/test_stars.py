#!/usr/bin/python

import glib
from gi.repository import Gtk
import mock
import os
import sys
import unittest

sys.path.insert(0,"../..")

from softwarecenter.ui.gtk3.widgets.stars import get_test_stars_window

class TestStars(unittest.TestCase):
    """ tests the stars widget """

    def test_stars(self):
        win = get_test_stars_window()
        win.show_all()
        glib.timeout_add_seconds(1, lambda: win.destroy())
        Gtk.main()

    # helper
    def _p(self):
        """ process gtk events """
        while Gtk.events_pending():
            Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
