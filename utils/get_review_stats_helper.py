#!/usr/bin/python

import pickle
import sys
import logging

from optparse import OptionParser

from softwarecenter.paths import *
from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # common options for optparse go here
    parser = OptionParser()

    # check options
    parser.add_option("--origin", default="any")
    parser.add_option("--distroseries", default="any")
    parser.add_option("--days-delta", default=None)
    parser.add_option("", "--debug",
                      action="store_true", default=False)
    (options, args) = parser.parse_args()

    if options.debug:
        LOG.setLevel(logging.DEBUG)

    cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
    rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)

    kwargs = {"origin": options.origin,
              "distroseries": options.distroseries,
             }
    if options.days_delta:
        kwargs["days"] = int(options.days_delta)

    # depending on the time delta, use a different call
    piston_review_stats = []
    try:
        piston_review_stats = rnrclient.review_stats(**kwargs)
    except:
        LOG.exception("get_review_stats")


    # print to stdout where its consumed by the parent
    print pickle.dumps(piston_review_stats)


