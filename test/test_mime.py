#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt_pkg
import apt
import os
import re
import unittest
import xapian

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.update import rebuild_database

class TestMime(unittest.TestCase):
    """ tests the mime releated stuff """

    def setUp(self):
        self.cache = AptCache()

    def test_most_popular_applications_for_mimetype(self):
        pathname = "../data/xapian"
        if not os.listdir(pathname):
            rebuild_database(pathname)
        db = StoreDatabase(pathname, self.cache)
        db.open()
        # all
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=False, num=5)
        self.assertEqual(len(result), 5)
        # only_uninstaleld
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=True, num=2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
