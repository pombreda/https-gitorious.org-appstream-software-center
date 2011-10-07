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

class TestViews(unittest.TestCase):

    def test_appview_search_combo(self):
        from softwarecenter.ui.gtk3.views.appview import get_test_window
        from softwarecenter.testutils import get_test_enquirer_matches

        # test if combox sort option "by relevance" vanishes for non-searches
        # LP: #861778
        expected_normal = ["By Name", "By Top Rated", "By Newest First"]
        expected_search = ["By Name", "By Top Rated", "By Newest First", 
                           "By Relevance"]

        # setup goo
        win = get_test_window()
        self._p()
        appview = win.get_data("appview")

        # test normal window (no search)
        model = appview.sort_methods_combobox.get_model()
        # collect items in the model
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        # this is what we expect there
        self.assertEqual(expected_normal, in_model)

        # now repeat and simulate a search
        matches = get_test_enquirer_matches(appview.helper.db)
        appview.display_matches(matches, is_search=True)
        self._p()
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        self.assertEqual(in_model, expected_search)

        # and back again to no search
        matches = get_test_enquirer_matches(appview.helper.db)
        appview.display_matches(matches, is_search=False)
        self._p()
        # collect items in the model
        in_model = []
        for item in model:
            in_model.append(model.get_value(item.iter, 0))
        self.assertEqual(expected_normal, in_model)

        # destroy
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def _p(self):
        for i in range(10):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
