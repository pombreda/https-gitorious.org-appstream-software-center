#!/usr/bin/python

import mock
import sys
import unittest
sys.path.insert(0,"../")
from softwarecenter.utils import *

sys.path.insert(0, "../utils")

class TestReviews(unittest.TestCase):
    """ tests the reviews """

    def test_gwibber_message(self):
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        mock_app.appname = "foo_app"
        mock_app.pkgname = "foo_pkg"
        sa = SubmitReviewsApp(mock_app, None, None, None, "../data")
        # short entry
        sa.review_summary_entry.set_text("summary")
        sa.star_rating.set_rating(1)
        self.assertEqual(sa._gwibber_message(), u"reviewed foo_app: \u2605\u2606\u2606\u2606\u2606 summary http://apt.ubuntu.com/p/foo_pkg")
        # long entry
        sa.review_summary_entry.set_text("long long review_summary long looong looooong looooooong loooooooong loooooooong loooooooong loooooooong loooooooong loooooooong loooooooong")
        sa.star_rating.set_rating(3)
        self.assertEqual(sa._gwibber_message(),  u"reviewed foo_app: \u2605\u2605\u2605\u2606\u2606 long long review_summary long looong looooong looooooong loooooooong loooooooong lo\u2026 http://apt.ubuntu.com/p/foo_pkg")
                         

    def test_gwibber_ui_label(self):
        # none
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "0"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, "../data")
        self.assertFalse(sa.gwibber_hbox.flags() & gtk.VISIBLE)
        # one
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "1"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, "../data")
        self.assertTrue(sa.gwibber_checkbutton.flags() & gtk.VISIBLE)
        self.assertEqual(sa.gwibber_checkbutton.get_label(), "Also post this review to Twitter (@randomuser)")
        # two
        os.environ["SOFTWARE_CENTER_GWIBBER_MOCK_USERS"] = "2"
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, "../data")
        self.assertTrue(sa.gwibber_checkbutton.flags() & gtk.VISIBLE)
        self.assertEqual(sa.gwibber_checkbutton.get_label(), "Also post this review to: ")

    def test_convert_rgba(self):
        from submit_review import SubmitReviewsApp
        mock_app = mock.Mock()
        sa = SubmitReviewsApp(mock_app, None, None, None, "../data")
        self.assertEqual(sa._convert_rgb_to_html(200, 0, 0),
                         "C80000")
        self.assertEqual(sa._convert_rgb_to_html(0, 0, 0),
                         "000000")
        self.assertEqual(sa._convert_rgb_to_html(10, 10, 10),
                         "0A0A0A")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
