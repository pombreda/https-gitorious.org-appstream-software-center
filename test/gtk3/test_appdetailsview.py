#!/usr/bin/python

import unittest
from gi.repository import Gtk, GObject

from testutils import setup_test_env
setup_test_env()

from mock import Mock, patch

from softwarecenter.db.application import Application
from softwarecenter.testutils import get_mock_app_from_real_app, do_events
from softwarecenter.ui.gtk3.views.appdetailsview import get_test_window_appdetails
from softwarecenter.enums import PkgStates

# window destory timeout
TIMEOUT=100

class TestAppdetailsView(unittest.TestCase):

    def setUp(self):
        self.win = get_test_window_appdetails()
        self.view = self.win.get_data("view")

    def tearDown(self):
        GObject.timeout_add(TIMEOUT, lambda: self.win.destroy())
        Gtk.main()

    def test_videoplayer(self):
        # show app with no video
        app = Application("", "2vcard")
        self.view.show_app(app)
        do_events()
        self.assertFalse(self.view.videoplayer.get_property("visible"))

        # create app with video and ensure its visible
        app = Application("", "synaptic")
        mock = get_mock_app_from_real_app(app)
        details = mock.get_details(None)
        # this is a example html - any html5 video will do
        details.video_url = "http://people.canonical.com/~mvo/totem.html"
        self.view.show_app(mock)
        do_events()
        self.assertTrue(self.view.videoplayer.get_property("visible"))
    
    def test_page(self):
        # show app 
        app = Application("", "software-center")
        self.view.show_app(app)
        do_events()

        # create mock app
        mock_app = get_mock_app_from_real_app(app)
        self.view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.purchase_date = "2011-11-20 17:45:01"
        mock_details._error_not_found = "error not found"
        self.view.app_details = mock_details

        # show a app through the various states
        for var in vars(PkgStates):
            # FIXME: this just ensures we are not crashing, also
            # add functional tests to ensure on error we show
            # the right info etc
            state = getattr(PkgStates, var)
            mock_details.pkg_state = state
            # reset app to ensure its shown again
            self.view.app = None
            # show it
            self.view.show_app(mock_app)

    def test_app_icon_loading(self):
        # get icon
        app = Application("", "software-center")
        mock_app = get_mock_app_from_real_app(app)
        self.view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.cached_icon_file_path = "download-icon-test"
        mock_details.icon = "favicon.ico"
        mock_details.icon_url = "http://de.wikipedia.org/favicon.ico"
        self.view.app_details = mock_details
        self.view.show_app(mock_app)
        do_events()
        # ensure the icon is there
        # FIXME: ensure that the icon is really downloaded
        #self.assertTrue(os.path.exists(mock_details.cached_icon_file_path))
        #os.unlink(mock_details.cached_icon_file_path)
        
    def test_add_where_is_it(self):
        app = Application("", "software-center")
        self.view.show_app(app)
        self.view._add_where_is_it_commandline("apt")
        do_events()
        self.view._add_where_is_it_launcher("/usr/share/applications/ubuntu-software-center.desktop")
        do_events()

    def test_reviews_page(self):
        win = get_test_window_appdetails()
        view = win.get_data("view")
        # show s-c and click on more review
        app = Application("", "software-center")
        view.show_app(app)
        self.assertEqual(view._reviews_server_page, 1)
        view._on_more_reviews_clicked(None)
        self.assertEqual(view._reviews_server_page, 2)
        # show different app, ensure page is reset
        app = Application("", "apt")
        view.show_app(app)
        self.assertEqual(view._reviews_server_page, 1)

    def test_pkgstatus_bar(self):
        # make sure configure is run with the various states
        # test
        # show app 
        app = Application("", "software-center")
        self.view.show_app(app)
        do_events()

        # create mock app
        mock_app = get_mock_app_from_real_app(app)
        self.view.app = mock_app
        mock_details = mock_app.get_details(None)
        mock_details.purchase_date = "2011-11-20 17:45:01"
        self.view.app_details = mock_details

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
            self.view.pkg_statusbar.configure(mock_details, state)

        # make sure the various states are tested for click
        self.view.pkg_statusbar.app_manager = mock = Mock()
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
            self.view.pkg_statusbar.pkg_state = state
            self.view.pkg_statusbar._on_button_clicked(mock_button)
            self.assertTrue(
                getattr(mock, func).called,
                "for state %s the function %s was not called" % (state, func))
            mock.reset()


    def test_switch_language_resets_page(self):
        self.view._reviews_server_page = 4

        self.view.reviews.emit("different-review-language-clicked", 'my')

        self.assertEqual(1, self.view._reviews_server_page)

    def test_switch_reviews_sort_method_resets_page(self):
        self.view._reviews_server_page = 4

        self.view.reviews.emit("review-sort-changed", 1)

        self.assertEqual(1, self.view._reviews_server_page)

    @patch('softwarecenter.backend.reviews.rnr.ReviewLoaderSpawningRNRClient'
           '.get_reviews')
    def test_no_reviews_returned_attempts_relaxing(self, mock_get_reviews):
        """AppDetailsView._reviews_ready_callback will attempt to drop the
           origin and distroseries restriction if no reviews are returned
           with the restrictions in place.
        """
        self.view._do_load_reviews()

        self.assertEqual(1, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

        # Now we come back with no data
        application, callback = mock_get_reviews.call_args[0]
        callback(application, [])

        self.assertEqual(2, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(True, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

    @patch('softwarecenter.backend.reviews.rnr.ReviewLoaderSpawningRNRClient'
           '.get_reviews')
    def test_all_duplicate_reviews_keeps_going(self, mock_get_reviews):
        """AppDetailsView._reviews_ready_callback will fetch another page if
           all data returned was already displayed in the reviews list.
        """
        # Fixme: Do we have a test factory?
        review = Mock()
        review.rating = 3
        review.date_created = "2011-01-01 18:00:00"
        review.version = "1.0"
        review.summary = 'some summary'
        review.review_text = 'Some text'
        review.reviewer_username = "name"
        review.reviewer_displayname = "displayname"

        reviews = [review]
        self.view.reviews.reviews = reviews
        self.view._do_load_reviews()

        self.assertEqual(1, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(1, kwargs['page'])

        # Now we come back with no NEW data
        application, callback = mock_get_reviews.call_args[0]
        callback(application, reviews)

        self.assertEqual(2, mock_get_reviews.call_count)
        kwargs = mock_get_reviews.call_args[1]
        self.assertEqual(False, kwargs['relaxed'])
        self.assertEqual(2, kwargs['page'])


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
