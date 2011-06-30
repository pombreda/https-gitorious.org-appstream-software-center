#!/usr/bin/python

import gtk
import mock
import os
import sys
import unittest

sys.path.insert(0,"../")

from softwarecenter.db.application import Application
from softwarecenter.backend.reviews import Review, get_review_loader
from softwarecenter.db.pkginfo import get_pkg_info

sys.path.insert(0, "../utils")

class TestReviews(unittest.TestCase):
    """ tests the reviews """

    def test_reviews_sorting_by_version(self):
        # new version
        a1 = Review(Application("", "foo_pkg1"))
        a1.id = 1
        a1.version = "1.0"
        # old version
        a2 = Review(Application("f", "foo_pkg2"))
        a2.id = 2
        a2.version = "0.1"
        # now ensure that the new version is sorted in front
        self.assertEqual(sorted([a2, a1], reverse=True), [a1, a2])

    def test_reviews_sorting_by_usefulness(self):
        # new version
        a1 = Review(Application("", "foo_pkg1"))
        a1.id = 1
        a1.usefulness_favorable = 20
        # also test that only upstream version is included in the compare
        # (see LP: #777583)
        a1.version = "1.0-0ubuntu1"
        # old version
        a2 = Review(Application("f", "foo_pkg2"))
        a2.id = 2
        a2.usefulness_favorable = 10
        a2.version = "1.0-0ubuntu2"
        # now ensure that the new version is sorted in front
        self.assertEqual(sorted([a2, a1], reverse=True), [a1, a2])

    def test_reviews_sorting_by_date(self):
        # new version
        a1 = Review(Application("", "foo_pkg1"))
        a1.date_created = "2012-01-01 10:00:00"
        a1.id = 1
        a1.usefulness_favorable = 10
        a1.version = "1.0"
        # old version
        a2 = Review(Application("f", "foo_pkg2"))
        a2.id = 2
        a2.date_created = "2011-01-01 10:00:00"
        a2.usefulness_favorable = 10
        a2.version = "1.0"
        # now ensure that the new version is sorted in front
        self.assertEqual(sorted([a2, a1], reverse=True), [a1, a2])

    def test_gwibber_message(self):
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        mock_app.pkgname = "foo_pkg"
        mock_app.name = "foo_app"
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        # short entry
        sa.review_summary_entry.set_text("summary")
        sa.star_rating.set_rating(1)
        self.assertEqual(sa._gwibber_message(), u"reviewed foo_app in Ubuntu: \u2605\u2606\u2606\u2606\u2606 summary ")
        # long entry
        sa.review_summary_entry.set_text("long long review_summary long looong looooong looooooong loooooooong loooooooong loooooooong loooooooong loooooooong loooooooong loooooooong")
        sa.star_rating.set_rating(3)
        gwibber_msg = sa._gwibber_message(max_len=141)
        self.assertEqual(len(gwibber_msg), 141)
        self.assertEqual(gwibber_msg,  u"reviewed foo_app in Ubuntu: \u2605\u2605\u2605\u2606\u2606 long long review_summary long looong looooong looooooong loooooooong loooooooong loooooooong loooooooong \u2026 ")

    def test_gwibber_ui_label(self):
        # none
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "0"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        self.assertFalse(sa.gwibber_hbox.flags() & gtk.VISIBLE)
        # one
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "1"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        self.assertTrue(sa.gwibber_checkbutton.flags() & gtk.VISIBLE)
        self.assertEqual(sa.gwibber_checkbutton.get_label(), "Also post this review to Twitter (@randomuser)")
        # two
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "2"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        self.assertTrue(sa.gwibber_checkbutton.flags() & gtk.VISIBLE)
        self.assertEqual(sa.gwibber_checkbutton.get_label(), "Also post this review to: ")

    def test_review_ui_send_to_multiple_accounts(self):
        # two accounts
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "2"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        mock_app.appname = "the app name"
        mock_app.pkgname = "apkg"
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        sa.quit = mock.Mock()
        sa.api = mock.Mock()
        # setup UI to point to "all gwibber accounts"
        sa.gwibber_checkbutton.set_active(True)
        sa.gwibber_combo.set_active(len(sa.gwibber_accounts)-1)
        self.assertEqual(sa.gwibber_combo.get_active(), 2)
        # this trigers the sending
        sa.gwibber_helper.send_message = mock.Mock()
        # FIXME: factor this out into a method
        sa.on_transmit_success(None, None)
        # check if send_message was called two times
        self.assertEqual(sa.gwibber_helper.send_message.call_count, 2)
        # check if the app would have terminated as expected
        self.assertTrue(sa.quit.called)
        self.assertEqual(sa.quit.call_args, ((), {}))

    def test_convert_rgba(self):
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, None, "../data")
        self.assertEqual(sa._convert_rgb_to_html(200, 0, 0),
                         "C80000")
        self.assertEqual(sa._convert_rgb_to_html(0, 0, 0),
                         "000000")
        self.assertEqual(sa._convert_rgb_to_html(10, 10, 10),
                         "0A0A0A")

    def test_get_top_rated_apps(self):
        cache = get_pkg_info()
        loader = get_review_loader(cache)
        top_rated = loader.get_top_rated_apps()
        self.assertEqual(len(top_rated), 12)
        #print top_rated

    # helper
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
