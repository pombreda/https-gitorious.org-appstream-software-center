# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gzip
import logging
import os
import json
import time

from softwarecenter.backend.spawn_helper import SpawnHelper
from softwarecenter.backends.reviews import ReviewLoader
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.backend.piston.rnrclient_pristine import ReviewDetails
from softwarecenter.db.database import Application
import softwarecenter.distro
from softwarecenter.netstatus import network_state_is_connected
from softwarecenter.paths import (SOFTWARE_CENTER_CACHE_DIR,
                                  PistonHelpers,
                                  )
from softwarecenter.utils import calc_dr

LOG = logging.getLogger(__name__)


# this code had several incernations: 
# - python threads, slow and full of latency (GIL)
# - python multiprocesing, crashed when accessibility was turned on, 
#                          does not work in the quest session (#743020)
# - GObject.spawn_async() looks good so far (using the SpawnHelper code)
class ReviewLoaderSpawningRNRClient(ReviewLoader):
    """ loader that uses multiprocessing to call rnrclient and
        a glib timeout watcher that polls periodically for the
        data 
    """

    def __init__(self, cache, db, distro=None):
        super(ReviewLoaderSpawningRNRClient, self).__init__(cache, db, distro)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
        self.rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)
        self._reviews = {}

    def _update_rnrclient_offline_state(self):
        # this needs the lp:~mvo/piston-mini-client/offline-mode branch
        self.rnrclient._offline_mode = not network_state_is_connected()

    # reviews
    def get_reviews(self, translated_app, callback, page=1, 
                    language=None, sort=0):
        """ public api, triggers fetching a review and calls callback
            when its ready
        """
        # its fine to use the translated appname here, we only submit the
        # pkgname to the server
        app = translated_app
        self._update_rnrclient_offline_state()
        sort_method = self._review_sort_methods[sort]
        if language is None:
            language = self.language
        # gather args for the helper
        try:
            origin = self.cache.get_origin(app.pkgname)
        except:
            # this can happen if e.g. the app has multiple origins, this
            # will be handled later
            origin = None
        # special case for not-enabled PPAs
        if not origin and self.db:
            details = app.get_details(self.db)
            ppa = details.ppaname
            if ppa:
                origin = "lp-ppa-%s" % ppa.replace("/", "-")
        # if there is no origin, there is nothing to do
        if not origin:
            callback(app, [])
            return
        distroseries = self.distro.get_codename()
        # run the command and add watcher
        cmd = [os.path.join(softwarecenter.paths.datadir, PistonHelpers.GET_REVIEWS),
               "--language", language, 
               "--origin", origin, 
               "--distroseries", distroseries, 
               "--pkgname", str(app.pkgname), # ensure its str, not unicode
               "--page", str(page),
               "--sort", sort_method,
              ]
        spawn_helper = SpawnHelper()
        spawn_helper.connect(
            "data-available", self._on_reviews_helper_data, app, callback)
        spawn_helper.run(cmd)

    def _on_reviews_helper_data(self, spawn_helper, piston_reviews, app, callback):
        # convert into our review objects
        reviews = []
        for r in piston_reviews:
            reviews.append(Review.from_piston_mini_client(r))
        # add to our dicts and run callback
        self._reviews[app] = reviews
        callback(app, self._reviews[app])
        return False

    # stats
    def refresh_review_stats(self, callback):
        """ public api, refresh the available statistics """
        try:
            mtime = os.path.getmtime(self.REVIEW_STATS_CACHE_FILE)
            days_delta = int((time.time() - mtime) // (24*60*60))
            days_delta += 1
        except OSError:
            days_delta = 0
        LOG.debug("refresh with days_delta: %s" % days_delta)
        #origin = "any"
        #distroseries = self.distro.get_codename()
        cmd = [os.path.join(
                softwarecenter.paths.datadir, PistonHelpers.GET_REVIEW_STATS),
               # FIXME: the server currently has bug (#757695) so we
               #        can not turn this on just yet and need to use
               #        the old "catch-all" review-stats for now
               #"--origin", origin, 
               #"--distroseries", distroseries, 
              ]
        if days_delta:
            cmd += ["--days-delta", str(days_delta)]
        spawn_helper = SpawnHelper()
        spawn_helper.connect("data-available", self._on_review_stats_data, callback)
        spawn_helper.run(cmd)

    def _on_review_stats_data(self, spawn_helper, piston_review_stats, callback):
        """ process stdout from the helper """
        review_stats = self.REVIEW_STATS_CACHE

        if self._cache_version_old and self._server_has_histogram(piston_review_stats):
            self.REVIEW_STATS_CACHE = {}
            self.save_review_stats_cache_file()
            self.refresh_review_stats(callback)
            return

        # convert to the format that s-c uses
        for r in piston_review_stats:
            s = ReviewStats(Application("", r.package_name))
            s.ratings_average = float(r.ratings_average)
            s.ratings_total = float(r.ratings_total)
            if r.histogram:
                s.rating_spread = json.loads(r.histogram)
            else:
                s.rating_spread = [0,0,0,0,0]
            s.dampened_rating = calc_dr(s.rating_spread)
            review_stats[s.app] = s
        self.REVIEW_STATS_CACHE = review_stats
        callback(review_stats)
        self.save_review_stats_cache_file()

    def _server_has_histogram(self, piston_review_stats):
        '''check response from server to see if histogram is supported'''
        supported = getattr(piston_review_stats[0], "histogram", False)
        if not supported:
            return False
        return True
