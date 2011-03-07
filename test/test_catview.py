#!/usr/bin/python

import gtk
import sys
import unittest


sys.path.insert(0,"../")
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.catview_gtk import LobbyViewGtk, SubCategoryViewGtk
from softwarecenter.paths import *
from softwarecenter.distro import get_distro

class TestLobbyViewGtk(unittest.TestCase):

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
        self.lobbyview = LobbyViewGtk(
            datadir, self.desktopdir, cache, db, icons, None)
        self.lobbyview.show_all()

    def test_categories_in_view(self):
        self.assertTrue(
            self.lobbyview.whatsnew_carousel.get_property("visible"))
        self.assertTrue(
            self.lobbyview.featured_carousel.get_property("visible"))
        self.assertEqual(self.lobbyview.header, "Departments")

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
        # FIXME: this needs to move out of the CategoriesView class
        cats = self.subcatview.parse_applications_menu(self.desktopdir)
        # FIXME: this needs a proper API
        cat_games = [c for c in cats if c.untranslated_name == "Games"][0]

        # set to games
        self.subcatview.set_subcategory(cat_games)
        # and see that the UI is ok
        self._p()
        self.assertEqual(self.subcatview.header, "Games")
        self.assertTrue(self.subcatview.subcat_label.get_property("visible"))
        self.assertEqual(self.subcatview.subcat_label.get_text(), "Games")
        children = self.subcatview.departments._non_col_children
        #print children
        self.assertTrue(len(children) > 4)
        self.assertTrue(self.subcatview.departments.n_columns >= 1)
        for w in children:
            self.assertTrue(w.get_property("visible"))
        # test the first UI element specifically
        self.assertEqual(children[0].label.get_text(), "Arcade")
        self.assertEqual(children[0].image.get_icon_name()[0],
                         "applications-arcade")

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

       

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
