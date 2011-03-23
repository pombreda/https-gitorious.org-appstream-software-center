#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import glib
import gtk
import unittest

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.appview import AppView, AppStore
from softwarecenter.paths import *

import xapian

class MockAppViewFilter(object):
    @property
    def required(self):
        return False

class TestAppStore(unittest.TestCase):
    """ tests the AppStore GtkTreeViewModel """

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.mock_filter = MockAppViewFilter()

    def test_appview_ui(self):
        # create window
        win = gtk.Window()
        win.set_size_request(400,300)
        box = gtk.HBox()
        win.add(box)
        win.show_all()
        icons = gtk.icon_theme_get_default()
        store = AppStore(
            self.cache, self.db, icons,
            search_query = xapian.Query("apt"),
            limit=0,
            nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE)
        # create view
        view = AppView(show_ratings=False, store=store)
        view.show()
        scroll = gtk.ScrolledWindow()
        scroll.add(view)
        scroll.show()
        box.pack_start(scroll)
        self._p()
        # FIXME: test more interessting stuff
        self.assertTrue(view.get_property("visible"))
        win.destroy()

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
