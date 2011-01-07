#!/usr/bin/python

import mock
import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.utils import *

class TestReviews(unittest.TestCase):
    """ tests the reviews """

    def test_convert_rgba(self):
        sys.path.insert(0, "../utils")
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
