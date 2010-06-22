#!/usr/bin/python


import sys
sys.path.insert(0,"../")

import apt
import unittest

import xapian
from softwarecenter.enums import *

class testXapian(unittest.TestCase):
    """ tests the xapian database """

    def setUp(self):
        # FIXME: create a fixture DB instead of using the system one
        # but for now that does not matter that much, only if we
        # call open the db is actually read and the path checked
        dbpath = "/var/cache/software-center/xapian"
        self.xapiandb = xapian.Database(dbpath)
        self.enquire = xapian.Enquire(self.xapiandb)

    def test_exact_query(self):
        query = xapian.Query("APsoftware-center")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertEqual(len(matches), 1)

    def test_search_term(self):
        search_term = "apt"
        parser = xapian.QueryParser()
        query = parser.parse_query(search_term)
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

    def test_category_query(self):
        search_term = "apt"
        query = xapian.Query("ACaudiovideo")
        self.enquire.set_query(query)
        matches = self.enquire.get_mset(0, 100)
        self.assertTrue(len(matches) > 5)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
