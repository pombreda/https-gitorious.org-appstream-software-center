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

    def test_human_readable_name_in_view(self):
        model = self.view.reviews.review_language.get_model()
        self.assertEqual(model[0][0], "English")

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
            self.view.pkg_statusbar.app_manager = mock = Mock()
            self.view.pkg_statusbar.pkg_state = state
            self.view.pkg_statusbar._on_button_clicked(Mock())
            self.assertTrue(
                getattr(mock, func).called,
                "for state %s the function %s was not called" % (state, func))

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

    @patch('softwarecenter.backend.spawn_helper.SpawnHelper.run')
    def test_submit_new_review_disables_button(self, mock_run):
        button = self.view.reviews.new_review
        self.assertTrue(button.is_sensitive())

        button.emit('clicked')

        self.assertFalse(button.is_sensitive())

    def test_new_review_dialog_closes_reenables_submit_button(self):
        button = self.view.reviews.new_review
        button.disable()

        self.view._submit_reviews_done_callback(None, 0)

        self.assertTrue(button.is_sensitive())


class AppDetailsStatusBarTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        from softwarecenter.testutils import get_test_db
        cls.db = get_test_db()

    def setUp(self):
        self.win = get_test_window_appdetails()
    
    def tearDown(self):
        GObject.timeout_add(TIMEOUT, lambda: self.win.destroy())
        Gtk.main()

    def _make_statusbar_view_for_state(self, state):
        app_details = self._make_app_details()
        # XXX 2011-01-23 It's unfortunate we need multiple mocks to test this
        # correctly, but I don't know the code well enough to refactor
        # dependencies yet. In this case, we need a *real* app details object
        # for displaying in the view, but want to specify its state for the
        # purpose of the test. As an Application normally loads its details
        # from the database, we patch Application.get_details also.
        # Patch app_details.pkg_state for the test.
        pkg_state_fn = 'softwarecenter.db.application.AppDetails.pkg_state'
        pkg_state_patcher = patch(pkg_state_fn)
        self.addCleanup(pkg_state_patcher.stop)
        mock_pkg_state = pkg_state_patcher.start()
        mock_pkg_state.__get__ = Mock(return_value=state)

        get_details_fn = 'softwarecenter.db.application.Application.get_details'
        get_details_patcher = patch(get_details_fn)
        self.addCleanup(get_details_patcher.stop)
        mock_get_details = get_details_patcher.start()
        mock_get_details.return_value = app_details

        app = app_details._app
        details_view = self.win.get_data("view")
        details_view.show_app(app)
        do_events()

        statusbar_view = details_view.pkg_statusbar
        statusbar_view.configure(app_details, state)

        return statusbar_view

    def _make_app_details(self, supported_series=None):
        subscription = {
            u'application': {
                u'archive_id': u'commercial-ppa-uploaders/photobomb',
                u'description': u"Easy and Social Image Editor\nPhotobomb "
                                u"give you easy access to images in your "
                                u"social networking feeds, pictures on ...",
                u'name': u'Photobomb',
                u'package_name': u'photobomb',
                u'signing_key_id': u'1024R/75254D99'
                },
            u'deb_line': u'deb https://some.user:ABCDEFGHIJKLMNOP@'
                         u'private-ppa.launchpad.net/commercial-ppa-uploaders/'
                         u'photobomb/ubuntu natty main',
            u'distro_series': {u'code_name': u'natty', u'version': u'11.04'},
            u'failures': [],
            u'open_id': u'https://login.ubuntu.com/+id/ABCDEF',
            u'purchase_date': u'2011-09-16 06:37:52',
            u'purchase_price': u'2.99',
            u'state': u'Complete',
            }

        from softwarecenter.distro import get_distro
        distro = get_distro()
        if supported_series != None:
            subscription['application']['series'] = supported_series
        else:
            # If no supportod_series kwarg was provided, we ensure the
            # current series/arch is supported.
            subscription['application']['series'] = {
                distro.get_codename(): [distro.get_architecture()]
                }

        from piston_mini_client import PistonResponseObject
        from softwarecenter.db.update import (
            make_doc_from_parser,
            SCAPurchasedApplicationParser,
            )
        item = PistonResponseObject.from_dict(subscription)
        parser = SCAPurchasedApplicationParser(item)
        doc = make_doc_from_parser(parser, self.db._aptcache)
        from softwarecenter.db.application import AppDetails
        app_details = AppDetails(self.db, doc)
        return app_details

    def test_NOT_AVAILABLE_FOR_SERIES_no_action_for_click_event(self):
        statusbar_view = self._make_statusbar_view_for_state(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES)
        mock_app_manager = Mock()
        statusbar_view.app_manager = mock_app_manager
        mock_button = Mock()

        statusbar_view._on_button_clicked(mock_button)

        self.assertEqual([], mock_app_manager.method_calls)

    def test_NOT_AVAILABLE_FOR_SERIES_sets_label_and_button(self):
        statusbar_view = self._make_statusbar_view_for_state(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES)

        self.assertEqual(
            "Purchased on 2011-09-16 but not available for your current "
            "Ubuntu version. Please contact the vendor for an update.",
            statusbar_view.label.get_text())
        self.assertFalse(statusbar_view.button.get_visible())


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
