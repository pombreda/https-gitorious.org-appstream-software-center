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

    def test_installedpane(self):
        sys.argv.append('TESTING_USE_BLOCKING_QUERIES_ONLY')

        from softwarecenter.ui.gtk3.panes.installedpane import get_test_window
        win = get_test_window()
        installedpane = win.get_data("pane")
        installedpane.on_search_terms_changed(None, "the")
        self._p()
        model = installedpane.app_view.tree_view.get_model()
        len1 = len(model)
        installedpane.on_search_terms_changed(None, "nosuchsearchtermforsure")
        self._p()
        len2 = len(model)
        self.assertTrue(len2 < len1)
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
