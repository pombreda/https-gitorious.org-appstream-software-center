#!/usr/bin/python

import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.enums import *
from softwarecenter.utils import *

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.application import Application, AppDetails

import gmenu

class TestWhereIsit(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        datadir = "../data"
        cache = AptCache()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.db = StoreDatabase(pathname, cache)
        self.db.open()

    def search_gmenu_dir(self, dirlist, needle):
        for item in dirlist[-1].get_contents():
            mtype = item.get_type()
            if mtype == gmenu.TYPE_DIRECTORY:
                self.search_gmenu_dir(dirlist+[item], needle)
            elif item.get_type() == gmenu.TYPE_ENTRY:
                if os.path.basename(item.get_desktop_file_path()) == needle:
                    self.found = dirlist

    def test_where_is_it_applications(self):
        app = Application("Hardware Drivers", "jockey-gtk")
        details = app.get_details(self.db)
        self.assertEqual(details.desktop_file, 
                         "/usr/share/app-install/desktop/jockey-gtk.desktop")
        # search the settings menu
        self.found = None
        tree = gmenu.lookup_tree("settings.menu")
        self.search_gmenu_dir([tree.get_root_directory()], 
                              os.path.basename(details.desktop_file))
        self.assertEqual(self.found[0].get_name(), "System")
        self.assertEqual(self.found[0].get_icon(), "preferences-other")
        self.assertEqual(self.found[1].get_name(), "Administration")
        self.assertEqual(self.found[1].get_icon(), "preferences-system")
        # search the applications menu
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
