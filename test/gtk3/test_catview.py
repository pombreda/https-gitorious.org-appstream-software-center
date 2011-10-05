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
        # encoding is utf-8 (since r2218, see category.py)
        self.assertEqual(self._cat.name, 'What\xe2\x80\x99s New')
        self.assertEqual(self._cat.sortmode, SortMethods.BY_CATALOGED_TIME)

    def test_subcatview_new_no_sort_info_yet(self):
        # ensure that we don't show a empty "whats new" category
        # see LP: #865985
        from softwarecenter.testutils import get_test_db
        db = get_test_db()
        cache = db._aptcache
        # simulate a fresh install with no catalogedtime info
        del db._axi_values["catalogedtime"]
        
        from softwarecenter.testutils import get_test_gtk3_icon_cache
        icons = get_test_gtk3_icon_cache()

        from softwarecenter.db.appfilter import AppFilter
        apps_filter = AppFilter(db, cache)

        from softwarecenter.distro import get_distro
        import softwarecenter.paths
        from softwarecenter.paths import APP_INSTALL_PATH
        from softwarecenter.ui.gtk3.views.catview_gtk import LobbyViewGtk
        view = LobbyViewGtk(softwarecenter.paths.datadir, APP_INSTALL_PATH,
                            cache, db, icons, get_distro(), apps_filter)
        view.show()

        # gui
        win = Gtk.Window()
        win.set_size_request(800, 400)

        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        scroll.show()
        win.add(scroll)
        win.show()
        # test visibility
        self._p()
        self.assertFalse(view.new_frame.get_property("visible"))
        self._p()

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
