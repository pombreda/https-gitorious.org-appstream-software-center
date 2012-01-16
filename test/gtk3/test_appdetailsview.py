#!/usr/bin/python

import sys
import unittest

sys.path.insert(0, "..")
from softwarecenter.testutils import setup_test_env
setup_test_env()

from mock import Mock

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
        do_events()
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
    
    def test_page(self):
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show app 
        app = Application("", "software-center")
        view.show_app(app)
        do_events()

        # create mock app
        mock_app = get_mock_app_from_real_app(app)
        view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.purchase_date = "2011-11-20 17:45:01"
        mock_details._error_not_found = "error not found"
        view.app_details = mock_details

        # show a app through the various states
        for var in vars(PkgStates):
            # FIXME: this just ensures we are not crashing, also
            # add functional tests to ensure on error we show
            # the right info etc
            state = getattr(PkgStates, var)
            mock_details.pkg_state = state
            # reset app to ensure its shown again
            view.app = None
            # show it
            view.show_app(mock_app)

    def test_app_icon_loading(self):
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # get icon
        app = Application("", "software-center")
        mock_app = get_mock_app_from_real_app(app)
        view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.cached_icon_file_path = "download-icon-test"
        mock_details.icon = "favicon.ico"
        mock_details.icon_url = "http://de.wikipedia.org/favicon.ico"
        view.app_details = mock_details
        view.show_app(mock_app)
        do_events()
        # ensure the icon is there
        # FIXME: ensure that the icon is really downloaded
        #self.assertTrue(os.path.exists(mock_details.cached_icon_file_path))
        #os.unlink(mock_details.cached_icon_file_path)
        
    def test_add_where_is_it(self):
        win = get_test_window_appdetails()
        view = win.get_data("view")
        app = Application("", "software-center")
        view.show_app(app)
        view._add_where_is_it_commandline("apt")
        do_events()
        view._add_where_is_it_launcher("/usr/share/applications/ubuntu-software-center.desktop")
        do_events()

    def test_pkgstatus_bar(self):
        # make sure configure is run with the various states
        # test
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show app 
        app = Application("", "software-center")
        view.show_app(app)
        do_events()

        # create mock app
        mock_app = get_mock_app_from_real_app(app)
        view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.purchase_date = "2011-11-20 17:45:01"
        view.app_details = mock_details

        # run the configure on the various states for the pkgstatus bar
        for var in vars(PkgStates):
            # FIXME: this just ensures we are not crashing, also
            # add functional tests to ensure on error we show
            # the right info etc
            state = getattr(PkgStates, var)
            mock_details.pkg_state = state
            # FIXME2: we should make configure simpler and/or explain
            #         why it gets the state instead of just reading it
            #         from the app_details
            view.pkg_statusbar.configure(mock_details, state)

        # make sure the various states are tested for click
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
