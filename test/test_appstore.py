#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import random
import glib
import gtk
import shutil
import unittest

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.application import Application
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.appview import AppView, AppStore
from softwarecenter.enums import *
from softwarecenter.paths import *

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

class TestAppStore(unittest.TestCase):
    """ tests the AppStore GtkTreeViewModel """

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.cache.open()
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
        # deduplicate (kill off) pkgs with desktop files
        enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                       query, xapian.Query("XD")))
        valueno = self.db._axi_values["catalogedtime"]
        sorter = xapian.MultiValueKeyMaker()
        # second arg is forward-sort
        sorter.add_value(int(valueno), False)
        sorter.add_value(XAPIAN_VALUE_PKGNAME, True)
        enquire.set_sort_by_key(sorter)

        matches = enquire.get_mset(0, 10)
        for m in matches:
            doc = db.get_document(m.docid)
            #print xapian.sortable_unserialise(doc.get_value(valueno))
            sorted_by_axi.append(self.db.get_pkgname(doc))
        # now compare to what we get from the store
        sorted_by_appstore = []
        # we don't want to include items for purchase in the compare,
        # since although tagged with cataloged_time values, they don't
        # actually appear in the axi
        for_purchase_query = xapian.Query("AH" + AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME)
        store_query = xapian.Query(xapian.Query.OP_AND_NOT, 
                                   query, for_purchase_query)
        store = AppStore(self.cache, self.db, self.mock_icons, 
                         sortmode=SORT_BY_CATALOGED_TIME,
                         limit=10, search_query=store_query,
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

    def test_concurrent_searches(self):
        terms = [ "app", "this", "the", "that", "foo", "tool", "game", 
                  "graphic", "ubuntu", "debian", "gtk" "this", "bar", 
                  "baz"]

        # run a bunch of the querries in parallel
        for i in range(10):
            for term in terms:
                icons = gtk.icon_theme_get_default()
                store = AppStore(
                    self.cache, self.db, icons,
                    search_query = xapian.Query(term),
                    limit=0,
                    nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE)
                # extra fun
                glib.timeout_add(10, store._threaded_perform_search)
            self._p()

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
