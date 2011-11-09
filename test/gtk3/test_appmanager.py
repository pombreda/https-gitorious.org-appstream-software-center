#!/usr/bin/python

from gi.repository import Gtk
import unittest

import sys
sys.path.insert(0,"../")

import softwarecenter.paths
from softwarecenter.db.application import Application
from softwarecenter.distro import get_distro
from softwarecenter.testutils import (
    get_test_db, get_test_install_backend, get_test_gtk3_icon_cache,
    start_dummy_backend, stop_dummy_backend)
from softwarecenter.ui.gtk3.session.appmanager import (
    ApplicationManager, get_appmanager)

class TestAppManager(unittest.TestCase):
    """ tests the appmanager  """

    def setUp(self):
        # create dummy daemon so that we can run all commands for real
        start_dummy_backend()
        # get required test stuff
        self.db = get_test_db()
        self.backend = get_test_install_backend()
        self.distro = get_distro()
        self.datadir = softwarecenter.paths.datadir
        self.icons = get_test_gtk3_icon_cache()
        # create it once, it becomes global instance
        if get_appmanager() is None:
            app_manager = ApplicationManager(
                self.db, self.backend, self.distro, self.datadir, self.icons)

    def tearDown(self):
        stop_dummy_backend()

    def test_get_appmanager(self):
        app_manager = get_appmanager()
        self.assertNotEqual(app_manager, None)
        # test singleton
        app_manager2 = get_appmanager()
        self.assertEqual(app_manager, app_manager2)
        # test creating it twice raises a error
        self.assertRaises(
            ValueError, ApplicationManager, self.db, self.backend, self.distro,
            self.datadir, self.icons)
        
    def test_appmanager(self):
        app_manager = get_appmanager()
        self.assertNotEqual(app_manager, None)
        # dummy app
        app = Application("", "2vcard")
        # test interface
        app_manager.reload()
        app_manager.install(app, [], [])
        app_manager.remove(app, [], [])
        app_manager.upgrade(app, [], [])
        app_manager.apply_changes(app, [], [])
        app_manager.buy_app(app)
        app_manager.reinstall_purchased(app)
        app_manager.enable_software_source(app)
        while Gtk.events_pending():
            Gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
