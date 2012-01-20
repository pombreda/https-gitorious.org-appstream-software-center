#!/usr/bin/python

import os
import unittest

from gi.repository import GObject

from testutils import setup_test_env
setup_test_env()
from gettext import gettext as _

from softwarecenter.backend.reviews.rnr import (
    ReviewLoaderSpawningRNRClient as ReviewLoader)
from softwarecenter.testutils import get_test_pkg_info, get_test_db
from softwarecenter.backend.reviews.rnr_helpers import SubmitReviewsApp


class TestReviewLoader(unittest.TestCase):
    cache = get_test_pkg_info()
    db = get_test_db()

    def _review_stats_ready_callback(self, review_stats):
        self._stats_ready = True
        self._review_stats = review_stats

    def test_review_stats_caching(self):
        self._stats_ready = False
        self._review_stats = []
        review_loader = ReviewLoader(self.cache, self.db)
        review_loader.refresh_review_stats(self._review_stats_ready_callback)
        while not self._stats_ready:
            self._p()
        self.assertTrue(len(self._review_stats) > 0)
        self.assertTrue(os.path.exists(review_loader.REVIEW_STATS_CACHE_FILE))
        self.assertTrue(os.path.exists(review_loader.REVIEW_STATS_BSDDB_FILE))
        # once its there, get_top_rated
        top_rated = review_loader.get_top_rated_apps(quantity=10)
        self.assertEqual(len(top_rated), 10)
        # and per-cat
        top_cat = review_loader.get_top_rated_apps(
            quantity=8, category="Internet")
        self.assertEqual(len(top_cat), 8)

    def test_edit_review_screen_has_right_labels(self):
        """Check that LP #880255 stays fixed. """

        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='modify', review_id=10000)
        # monkey patch away login to avoid that we actually login
        # and the UI changes because of that
        review_app.login = lambda: True

        # run the main app
        review_app.run()

        self._p()
        review_app.login_successful('foobar')
        self._p()
        self.assertEqual(_('Rating:'), review_app.rating_label.get_label())
        self.assertEqual(_('Summary:'),
            review_app.review_summary_label.get_label())
        self.assertEqual(_('Review by: %s') % 'foobar',
            review_app.review_label.get_label())
        review_app.submit_window.hide()

    def test_get_fade_colour_markup(self):
        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='modify', review_id=10000)
        cases = (
            (('006000', '00A000', 40, 60, 50), ('008000', 10)),
            (('000000', 'FFFFFF', 40, 40, 40), ('000000', 0)),
            (('000000', '808080', 100, 400, 40), ('000000', 360)),
            (('000000', '808080', 100, 400, 1000), ('808080', -600)),
            (('123456', '5294D6', 10, 90, 70), ('427CB6', 20)),
            )
        for args, return_value in cases:
            result = review_app._get_fade_colour_markup(*args)
            expected = '<span fgcolor="#%s">%s</span>' % return_value
            self.assertEqual(expected, result)

    def test_modify_review_is_the_same_supports_unicode(self):
        """_modify_review_is_the_same should return True if we haven't changed
        the review at all, even if the review text contains non-ascii chars.
        """
        review_app = SubmitReviewsApp(datadir="../data", app=None,
            parent_xid='', iconname='accessories-calculator', origin=None,
            version=None, action='modify', review_id=10000)
        self.assertTrue(review_app._modify_review_is_the_same())

    def _p(self):
        main_loop = GObject.main_context_default()
        while main_loop.pending():
            main_loop.iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
