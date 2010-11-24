#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.application import Application
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.appview import AppStore
from softwarecenter.enums import *

import xapian

class MockAppViewFilter(object):
    @property
    def required(self):
        return False

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
            self.cache, self.db, self.mock_icons, 
            sortmode=SORT_BY_ALPHABET, 
            filter=self.mock_filter)
        self.assertTrue(len(store) > 0)

    def test_search(self):
        """ test if searching works """
        search_query = xapian.Query("APsoftware-center")
        store = AppStore(
            self.cache, self.db, self.mock_icons, search_query=search_query,
            sortmode=SORT_BY_ALPHABET, 
            filter=self.mock_filter)
        self.assertTrue(len(store) == 1)

    def test_sort_by_cataloged_time(self):
        # use axi to sort-by-cataloged-time
        sorted_by_axi = []
        db = xapian.Database("/var/lib/apt-xapian-index/index")
        query = xapian.Query("")
        enquire = xapian.Enquire(db)
        enquire.set_query(query)
        valueno = self.db._axi_values["catalogedtime"]
        
        # FIXME: use MultiValueKeyMaker instead once we have python
        #        bindings, sort by newness first and then by pkgname
        sorter = xapian.MultiValueSorter()
        # second arg is forward-sort
        sorter.add(int(valueno), True)
        sorter.add(XAPIAN_VALUE_PKGNAME)
        enquire.set_sort_by_key(sorter)

        matches = enquire.get_mset(0, 20)
        for m in matches:
            doc = db.get_document(m.docid)
            #print xapian.sortable_unserialise(doc.get_value(valueno))
            sorted_by_axi.append(self.db.get_pkgname(doc))
        # now compare to what we get from the store
        sorted_by_appstore = []
        store = AppStore(self.cache, self.db, self.mock_icons, 
                         sortmode=SORT_BY_CATALOGED_TIME,
                         limit=20, search_query=query,
                         nonapps_visible=AppStore.NONAPPS_ALWAYS_VISIBLE)
        for item in store:
            sorted_by_appstore.append(item[AppStore.COL_PKGNAME])
        self.assertEqual(sorted_by_axi, sorted_by_appstore)

    def test_show_hide_nonapps(self):
        """ test if showing/hiding non-applications works """
        store = AppStore(
            self.cache, self.db, self.mock_icons,
            search_query = xapian.Query(""),    
            limit=0,
            nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE)
        nonapps_not_visible = len(store)
        store = AppStore(
            self.cache, self.db, self.mock_icons,
            search_query = xapian.Query(""),
            limit=0,
            nonapps_visible = AppStore.NONAPPS_ALWAYS_VISIBLE)
        nonapps_visible = len(store)
        self.assertTrue(nonapps_visible > nonapps_not_visible)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
