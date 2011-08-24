from gi.repository import Gtk
import os
import sys
import time
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

import softwarecenter.paths
# ensure datadir is pointing to the right place
softwarecenter.paths.datadir = os.path.join(
    os.path.dirname(__file__), "..", "..", 'data')

from softwarecenter.enums import SortMethods
from softwarecenter.db.categories import get_category_by_name

class TestCatView(unittest.TestCase):

    def _on_category_selected(self, subcatview, category):
        #print "**************", subcatview, category
        self._cat = category
    
    def test_subcatview_toprated(self):
        from softwarecenter.ui.gtk3.views.catview_gtk import get_test_window_catview
        # get the widgets we need
        win = get_test_window_catview()
        lobby = win.get_data("lobby")
        # test clicking toprated
        lobby.connect("category-selected", self._on_category_selected)
        lobby.toprated_frame.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Top Rated")
        self.assertEqual(self._cat.sortmode, SortMethods.BY_TOP_RATED)

    def test_subcatview_new(self):
        from softwarecenter.ui.gtk3.views.catview_gtk import get_test_window_catview
        # get the widgets we need
        win = get_test_window_catview()
        lobby = win.get_data("lobby")
        # test clicking new
        lobby.connect("category-selected", self._on_category_selected)
        lobby.new_frame.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, u'What\u2019s New')
        self.assertEqual(self._cat.sortmode, SortMethods.BY_CATALOGED_TIME)

        

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
