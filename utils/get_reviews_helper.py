#!/usr/bin/python

import pickle
import sys
import logging

from optparse import OptionParser

from softwarecenter.paths import *
from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI, ReviewDetails

LOG = logging.getLogger(__name__)

if __name__ == "__main__":

    # common options for optparse go here
    parser = OptionParser()

    # check options
    parser.add_option("--language")
    parser.add_option("--origin")
    parser.add_option("--distroseries")
    parser.add_option("--pkgname")
    parser.add_option("", "--debug",
                      action="store_true", default=False)
    (options, args) = parser.parse_args()

    if options.debug:
        LOG.setLevel(logging.DEBUG)

    cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
    rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)

    kwargs = {"language": options.language, 
              "origin": options.origin,
              "distroseries": options.distroseries,
              "packagename": options.pkgname,
              }
    piston_reviews = []
    try:
        piston_reviews = rnrclient.get_reviews(**kwargs)
        # the backend sometimes returns None so we fix this here
        if piston_reviews is None:
            piston_reviews = []
    except simplejson.decoder.JSONDecodeError, e:
        LOG.error("failed to parse '%s'" % e.doc)
    #bug lp:709408 - don't print 404 errors as traceback when api request 
    #                returns 404 error
    except APIError, e:
        LOG.warn("_get_reviews_threaded: no reviews able to be retrieved for package: %s (%s, origin: %s)" % (app.pkgname, distroseries, origin))
        LOG.debug("_get_reviews_threaded: no reviews able to be retrieved: %s" % e)
    except:
        LOG.exception("get_reviews")

    # print to stdout where its consumed by the parent
    print pickle.dumps(piston_reviews)


