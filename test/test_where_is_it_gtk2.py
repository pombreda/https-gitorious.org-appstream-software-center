#!/usr/bin/python

import os
import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.ui.gtk.gmenusearch import GMenuSearcher
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.application import Application

class TestWhereIsit(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        cache = get_pkg_info()
        cache.open()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.db = StoreDatabase(pathname, cache)
        self.db.open()

    def test_where_is_it_in_applications(self):
        app = Application("Calculator", "gcalctool")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/gcalctool:gcalctool.desktop")
        # search the settings menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(
            details.desktop_file,
            [os.path.abspath("./data/fake-applications.menu")])
        self.assertEqual(found[0].get_name(), "Applications")
        self.assertEqual(found[0].get_icon(), "applications-other")
        self.assertEqual(found[1].get_name(), "Accessories")
        self.assertEqual(found[1].get_icon(), "applications-utilities")
    
    def test_where_is_it_kde4(self):
        app = Application("", "ark")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/ark:kde4__ark.desktop")
        # search the settings menu
        searcher = GMenuSearcher()
        found = searcher.get_main_menu_path(
            details.desktop_file,
            [os.path.abspath("./data/fake-applications.menu")])
        self.assertEqual(found[0].get_name(), "Applications")
        self.assertEqual(found[0].get_icon(), "applications-other")
        self.assertEqual(found[1].get_name(), "Accessories")
        self.assertEqual(found[1].get_icon(), "applications-utilities")
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()