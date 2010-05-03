#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.appview import AppStore

from softwarecenter.enums import *

class MockAppViewFilter(object):
    def filter(self, doc, pkgname):
        return True

class MockIconCache(object):
    def connect(self, signal, func):
        return True
    def load_icon(self, name, size, flags):
        return None

class testAppStore(unittest.TestCase):

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.mock_icons = MockIconCache()
        self.mock_filter = MockAppViewFilter()

    def test_init(self):
        store = AppStore(
            self.cache, self.db, self.mock_icons, sort=True, filter=mock_filter)
        self.assertTrue(len(store) > 0)



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
