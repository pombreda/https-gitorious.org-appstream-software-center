#!/usr/bin/python

from gi.repository import Gtk
import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

from mock import Mock

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

from softwarecenter.db.application import Application
from softwarecenter.testutils import get_mock_app_from_real_app, do_events
from softwarecenter.ui.gtk3.views.appdetailsview import get_test_window_appdetails
from softwarecenter.enums import PkgStates

class TestAppdetailsView(unittest.TestCase):

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
        do_events()
        self.assertTrue(view.videoplayer.get_property("visible"))
    
    def test_pkgstatus_bar(self):
        # make sure configure is run with the various states
        # test
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show app 
        app = Application("", "software-center")
        view.show_app(app)
        do_events()

        # run the configure on the various states
        for var in vars(PkgStates):
            # FIXME: this just ensures we are not crashing, also
            # add functional tests to ensure on error we show
            # the right info etc
            state = getattr(PkgStates, var)
            view.pkg_statusbar.configure(view.app_details, state)

        # make sure the various states are tested on click
        view.pkg_statusbar.app_manager = mock = Mock()
        mock_button = Mock()
        button_to_function_tests = (
            (PkgStates.INSTALLED, "remove"),
            (PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED, "reinstall_purchased"),
            (PkgStates.NEEDS_PURCHASE, "buy_app"),
            (PkgStates.UNINSTALLED, "install"),
            (PkgStates.REINSTALLABLE, "install"),
            (PkgStates.UPGRADABLE, "upgrade"),
            (PkgStates.NEEDS_SOURCE, "enable_software_source")
        )
        for state, func in button_to_function_tests:
            view.pkg_statusbar.pkg_state = state
            view.pkg_statusbar._on_button_clicked(mock_button)
            self.assertTrue(
                getattr(mock, func).called,
                "for state %s the function %s was not called" % (state, func))
            mock.reset()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
