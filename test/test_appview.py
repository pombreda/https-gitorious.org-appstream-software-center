#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter import Application
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.appview import AppStore
from softwarecenter.enums import *

import xapian

class MockAppViewFilter(object):
    def filter(self, doc, pkgname):
        return True

class MockIconCache(object):
    def connect(self, signal, func):
        return True
    def load_icon(self, name, size, flags):
        return None
    def disconnect_by_func(self, func):
        return True

class testAppStore(unittest.TestCase):
    """ tests the AppStore GtkTreeViewModel """

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.mock_icons = MockIconCache()
        self.mock_filter = MockAppViewFilter()

    def test_init(self):
        """ test basic init of the AppStore model """
        store = AppStore(
            self.cache, self.db, self.mock_icons, sort=True, 
            filter=self.mock_filter)
        self.assertTrue(len(store) > 0)

    def test_search(self):
        """ test if searching works """
        search_query = xapian.Query("APsoftware-center")
        store = AppStore(
            self.cache, self.db, self.mock_icons, search_query=search_query,
            sort=True, filter=self.mock_filter)
        self.assertTrue(len(store) == 1)

    def test_internal_append_app(self):
        """ test if the interal _append_app works """
        store = AppStore(
            self.cache, self.db, self.mock_icons, sort=True, 
            filter=self.mock_filter)
        len_now = len(store)
        # the _append_app() is the function we test
        app = Application("the foobar app", "foo")
        store._append_app(app)
        self.assertTrue(len(store) == (len_now + 1))
        # test that it was inserted as the last element
        self.assertEqual(store.apps[-1].pkgname, "foo")
        # test that the app_index_map points to the right index integer
        # in the store
        self.assertEqual(store.apps[store.app_index_map[app]], app)
        # test that the pkgname_index_map points to the right index too
        self.assertEqual(store.apps[store.pkgname_index_map["foo"][0]], app)
        self.assertEqual(store.apps[store.pkgname_index_map["foo"][0]].pkgname, "foo")

    def test_internal_insert_app_sorted(self):
        """ test if the interal _insert_app_sorted works """
        store = AppStore(
            self.cache, self.db, self.mock_icons, sort=True, 
            filter=self.mock_filter)
        # create a store with some entries
        store.clear()
        for s in ["bb","dd","gg","ii"]:
            app = Application(s, s)
            store._append_app(app)
        # now test _insert_app_sorted
        test_data = [ (-2, "hh"),
                      ( 1, "cc"),    
                      ( 3, "ee"),
                      ( 0, "aa"),
                      (-1, "zz"),
                      (-2, "jj"),
                      (-2, "kk"),
                      ( 5, "ff"),
                    ]
        for (pos, s) in test_data:
            app = Application(s, s)
            store._insert_app_sorted(app)
            self.assertEqual(store.apps[pos], app)

        
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
