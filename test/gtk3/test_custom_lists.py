#!/usr/bin/python

from gi.repository import Gtk, GObject
import sys
import time
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

TIMEOUT=300

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

class TestSearch(unittest.TestCase):

    def test_custom_lists(self):
        from softwarecenter.ui.gtk3.panes.availablepane import get_test_window
        win = get_test_window()
        pane = win.get_data("pane")
        self._p()
        pane.on_search_terms_changed(None, "ark,artha,software-center")
        self._p()
        model = pane.app_view.tree_view.get_model()
        # custom list should return three items
        self.assertTrue(len(model) == 3)
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        


    def _p(self):
        for i in range(10):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    unittest.main()

