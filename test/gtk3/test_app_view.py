
import sys
import time
import unittest
import xapian

from gi.repository import Gtk

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

from softwarecenter.db.enquire import AppEnquire
from softwarecenter.enums import SortMethods

from softwarecenter.testutils import (get_test_db,
                                      get_test_pkg_info,
                                      get_test_gtk3_icon_cache,
                                      )

class TestAppView(unittest.TestCase):
    """ test the app view """

    def setUp(self):
        self.cache = get_test_pkg_info()
        self.icons = get_test_gtk3_icon_cache()
        self.db = get_test_db()

    def test_app_view(self):
        from softwarecenter.ui.gtk3.views.appview import get_test_window
        enquirer = AppEnquire(self.cache, self.db)
        enquirer.set_query(xapian.Query(""),
                           sortmode=SortMethods.BY_CATALOGED_TIME,
                           limit=10,
                           nonblocking_load=False)

        # get test window
        win = get_test_window()
        appview = win.get_data("appview")
        # set matches
        appview.clear_model()
        appview.display_matches(enquirer.matches)
        self._p()
        # verify that the order is actually the correct one
        model = appview.tree_view.get_model()
        docs_in_model = [item[0] for item in model]
        docs_from_enquirer = [m.document for m in enquirer.matches]
        self.assertEqual(len(docs_in_model), 
                         len(docs_from_enquirer))
        for i in range(len(docs_in_model)):
            self.assertEqual(self.db.get_pkgname(docs_in_model[i]),
                             self.db.get_pkgname(docs_from_enquirer[i]))

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
