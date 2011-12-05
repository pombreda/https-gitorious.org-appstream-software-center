#!/usr/bin/python

import os
import tempfile
import unittest

import sys
sys.path.insert(0,"../")

from gi.repository import GObject

import softwarecenter.paths
softwarecenter.paths.SOFTWARE_CENTER_CACHE_DIR = tempfile.mkdtemp()

from softwarecenter.backend.reviews.rnr import (
    ReviewLoaderSpawningRNRClient as ReviewLoader)
from softwarecenter.testutils import (get_test_pkg_info, get_test_db)

class TestReviewLoader(unittest.TestCase):

    def setUp(self):
        self.cache = get_test_pkg_info()
        self.db = get_test_db()

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
    

    def _p(self):
        main_loop = GObject.main_context_default()
        while main_loop.pending():
            main_loop.iteration()

if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
