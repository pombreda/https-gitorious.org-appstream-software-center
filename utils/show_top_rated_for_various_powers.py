#!/usr/bin/python

import sys
import unittest

sys.path.insert(0,"../")

from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import calc_dr

sys.path.insert(0, "../utils")


def show_top_rated_apps():
    # get the ratings
    cache = get_pkg_info()
    loader = get_review_loader(cache)
    review_stats = loader.REVIEW_STATS_CACHE
    # recalculate using different default power
    results = {}
    for i in [0.5, 0.4, 0.3, 0.2, 0.1, 0.05]:
        for (key, value) in review_stats.iteritems():
            value.dampened_rating = calc_dr(value.rating_spread, power=i)
        top_rated = loader.get_top_rated_apps()
        print "For power: %s" % i
        for item in top_rated:
            print review_stats[item]
        print 
        results[i] = top_rated[:]
        

if __name__ == "__main__":
    show_top_rated_apps()
