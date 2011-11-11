#!/usr/bin/python

from gi.repository import Gtk
import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

from softwarecenter.db.application import Application
from softwarecenter.testutils import get_mock_app_from_real_app
from softwarecenter.ui.gtk3.views.appdetailsview_gtk import get_test_window_appdetails
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

        # create app with video and ensure its visible
        app = Application("", "synaptic")
        mock = get_mock_app_from_real_app(app)
        details = mock.get_details(None)
        # this is a example html - any html5 video will do
        details.video_url = "http://people.canonical.com/~mvo/totem.html"
        view.show_app(mock)
        while Gtk.events_pending():
            Gtk.main_iteration()
        self.assertTrue(view.videoplayer.get_property("visible"))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
