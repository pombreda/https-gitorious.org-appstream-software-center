
import sys
import unittest
import xapian

from gi.repository import Gtk

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.database import StoreDatabase

from softwarecenter.ui.gtk3.models.appstore2 import AppListStore
from softwarecenter.db.enquire import AppEnquire

class TestAppstore(unittest.TestCase):
    """ test the appstore """

    def setUp(self):
        self.cache = get_pkg_info()
        self.cache.open()
        self.icons = Gtk.IconTheme.get_default()
        self.db = StoreDatabase(XAPIAN_BASE_PATH+"/xapian", self.cache)
        self.db.open()

    def test_app_store(self):
        # get a enquire object
        enquirer = AppEnquire(self.cache, self.db)
        enquirer.set_query(xapian.Query(""))

        # get a AppListStore and run functions on it
        model = AppListStore(self.db, self.cache, self.icons)

        # test if set from matches works
        self.assertEqual(len(model), 0)
        model.set_from_matches(enquirer.matches)
        self.assertTrue(len(model) > 0)
        # ensure the first row has a xapian doc type
        self.assertEqual(type(model[0][0]), xapian.Document)
        # lazy loading of the docs
        self.assertEqual(model[100][0], None)

        # test the load range stuff
        model.load_range(indices=[100], step=15)
        self.assertEqual(type(model[100][0]), xapian.Document)

        # ensure buffer_icons works and loads stuff into the cache
        model.buffer_icons()
        self.assertEqual(len(model.icon_cache), 0)
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.assertTrue(len(model.icon_cache) > 0)

        # ensure clear works
        model.clear()
        self.assertEqual(model.current_matches, None)
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
