#!/usr/bin/python

from gi.repository import Gtk, GObject
import sys
import time
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

TIMEOUT=3000

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

class TestSearch(unittest.TestCase):

    def test_installedpane(self):
        from softwarecenter.ui.gtk3.panes.installedpane import get_test_window
        win = get_test_window()
        installedpane = win.get_data("pane")
        self._p()
        # do simple search
        installedpane.on_search_terms_changed(None, "foo")
        self._p()
        model = installedpane.app_view.tree_view.get_model()
        len_only_apps = len(model)
        # set to show nonapps
        installedpane._show_nonapp_pkgs()
        self._p()
        len_with_nonapps = len(model)
        self.assertTrue(len_with_nonapps > len_only_apps)
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
