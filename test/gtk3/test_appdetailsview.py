#!/usr/bin/python

from gi.repository import Gtk, GObject
import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

from softwarecenter.ui.gtk3.views.appdetailsview_gtk import get_test_window_appdetails
from softwarecenter.db.application import Application

class TestAppdetailsViews(unittest.TestCase):

    def test_videoplayer(self):
        # get the widget
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show app with no video
        app = Application("", "2vcard")
        view.show_app(app)
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.assertFalse(view.videoplayer.get_property("visible"))
        # FIXME: create app with video and ensure its visible

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
