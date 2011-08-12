#!/usr/bin/python

from gi.repository import Gtk, GObject
import os
import subprocess
import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

from softwarecenter.ui.gtk3.panes.viewswitcher import get_test_window_viewswitcher
from softwarecenter.db.application import Application

TIMEOUT=300

class TestViews(unittest.TestCase):

    def setUp(self):
        self.aptd = subprocess.Popen(["aptd","--dummy", "--session-bus"])
        os.environ["SOFTWARE_CENTER_APTD_FAKE"] = "1"
        
    def tearDown(self):
        self.aptd.terminate()
        self.aptd.wait()

    def test_install_appdetails(self):
        from softwarecenter.ui.gtk3.views.appdetailsview_gtk import get_test_window_appdetails
        win = get_test_window_appdetails()
        view = win.get_data("view")
        view.show_app(Application("", "2vcard"))
        self._p()
        view.install()
        self._p()
        #Gtk.main()

    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
