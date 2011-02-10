#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import gtk
import shutil
import unittest


from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.application import Application
from softwarecenter.db.database import StoreDatabase
from softwarecenter.view.viewmanager import ViewManager
from softwarecenter.view.viewswitcher import ViewSwitcher, ViewSwitcherList
from softwarecenter.enums import *
from softwarecenter.paths import XAPIAN_BASE_PATH

import xapian

class testViewSwitcher(unittest.TestCase):
    """ tests the ViewSwitcher """

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.icons = gtk.icon_theme_get_default()
        self.datadir = "../data"
    def test_viewswitcher_simple(self):
        notebook = gtk.Notebook()
        manager = ViewManager(notebook)
        view = ViewSwitcher(manager, self.datadir, self.db, self.cache, 
                            self.icons)
        # pack it
        scroll = gtk.ScrolledWindow()
        scroll.add(view)
        win = gtk.Window()
        win.set_size_request(600, 400)
        win.add(scroll)
        win.show_all()
        self._p()
        # test it 
        model = view.get_model()
        # test for the right toplevels, if they have children and
        # are not expanded
        self.assertEqual(model[0][ViewSwitcherList.COL_NAME],
                         "Get Software")
        self.assertEqual(model.iter_has_child(model[0].iter), True)
        self.assertEqual(view.row_expanded(model[0].path), False)
        # and now for the installed one
        self.assertEqual(model[1][ViewSwitcherList.COL_NAME],
                         "Installed Software")
        self.assertEqual(model.iter_has_child(model[1].iter), True)
        self.assertEqual(view.row_expanded(model[1].path), False)

    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
