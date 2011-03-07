#!/usr/bin/python

import gtk
import sys
import unittest


sys.path.insert(0,"../")
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.catview_gtk import SubCategoryViewGtk
from softwarecenter.paths import *
from softwarecenter.distro import get_distro

class TestSubCatViewGtk(unittest.TestCase):

    def setUp(self):
        datadir = "../data"
        self.desktopdir = "/usr/share/app-install/"
        cache = AptCache()
        cache.open()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        db = StoreDatabase(pathname, cache)
        db.open()
        distro = get_distro()
        # icon mock
        icons = gtk.icon_theme_get_default()
        # create a details object
        self.subcatview = SubCategoryViewGtk(
            datadir, self.desktopdir, cache, db, icons, None)
        self.subcatview.show_all()

    def test_categories_in_view(self):
        cats = self.subcatview.parse_applications_menu(self.desktopdir)
        cat_games = [c for c in cats if c.untranslated_name == "Games"][0]

        self.subcatview.set_subcategory(cat_games)
        self.assertEqual(self.subcatview.header, "Games")

        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
