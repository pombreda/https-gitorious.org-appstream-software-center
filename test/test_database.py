#!/usr/bin/python


import sys
sys.path.insert(0,"../")

import apt
import unittest
import xapian

from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *

class testDatabase(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        # FIXME: create a fixture DB instead of using the system one
        # but for now that does not matter that much, only if we
        # call open the db is actually read and the path checked
        self.db = StoreDatabase("/var/cache/software-center/xapian", 
                                apt.Cache())
        #self.db.open()

    def test_comma_seperation(self):
        # normal
        querries = self.db._comma_expansion("apt,2vcard,7zip")
        self.assertEqual(len(querries), 3)
        # multiple identical
        querries = self.db._comma_expansion("apt,apt,apt")
        self.assertEqual(len(querries), 1)
        # too many commas
        querries = self.db._comma_expansion(",,,apt,xxx,,,")
        self.assertEqual(len(querries), 2)
        # invalid query
        querries = self.db._comma_expansion("??")
        self.assertEqual(querries, None)

    def test_update_from_desktop_file(self):
        from softwarecenter.db.update import update_from_app_install_data
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        cache = apt.Cache()
        res = update_from_app_install_data(db, cache, datadir="./data/")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)

    def test_update_from_var_lib_apt_lists(self):
        from softwarecenter.db.update import update_from_var_lib_apt_lists
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        cache = apt.Cache()
        res = update_from_var_lib_apt_lists(db, cache, listsdir="./data/app-info/")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
