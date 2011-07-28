#!/usr/bin/python

from gi.repository import Gtk, GdkPixbuf, GObject
import os
import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

from mock import Mock

from softwarecenter.ui.gtk3.panes.viewswitcher import get_test_window_viewswitcher

TIMEOUT=1

class TestViews(unittest.TestCase):

    def test_viewswitcher(self):
        import softwarecenter.paths
        softwarecenter.paths.datadir = "../data"
        win = get_test_window_viewswitcher()
        GObject.timeout_add_seconds(TIMEOUT, lambda: win.destroy())
        Gtk.main()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
