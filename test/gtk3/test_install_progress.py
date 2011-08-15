#!/usr/bin/python

from gi.repository import Gtk, GObject
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

from softwarecenter.db.application import Application
from softwarecenter.testutils import start_dummy_backend, stop_dummy_backend
from softwarecenter.ui.gtk3.panes.viewswitcher import (
    get_test_window_viewswitcher)

TIMEOUT=300

class TestViews(unittest.TestCase):

    def setUp(self):
        start_dummy_backend()
        time.sleep(1)
        
    def tearDown(self):
        stop_dummy_backend()

    def test_install_appdetails(self):
        from softwarecenter.ui.gtk3.views.appdetailsview_gtk import get_test_window_appdetails
        win = get_test_window_appdetails()
        view = win.get_data("view")
        view.show_app(Application("", "2vcard"))
        self._p()
        app = view.app
        view.backend.install(app.pkgname, app.appname, "")
        self._p()
        #Gtk.main()

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
