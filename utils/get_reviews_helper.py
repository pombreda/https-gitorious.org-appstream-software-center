#!/usr/bin/python

import os
import pickle
import simplejson
import logging

from optparse import OptionParser

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI

from piston_mini_client import APIError


LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # common options for optparse go here
    parser = OptionParser()

    # check options
    parser.add_option("--language", default="any")
    parser.add_option("--origin", default="any")
    parser.add_option("--distroseries", default="any")
    parser.add_option("--pkgname")
    parser.add_option("--version", default="any")
    parser.add_option("", "--debug",
                      action="store_true", default=False)
    parser.add_option("--no-pickle",
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
              "version": options.version,
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
        LOG.warn("_get_reviews_threaded: no reviews able to be retrieved for package: %s (%s, origin: %s)" % (options.pkgname, options.distroseries, options.origin))
        LOG.debug("_get_reviews_threaded: no reviews able to be retrieved: %s" % e)
    except:
        LOG.exception("get_reviews")

    # useful for debugging        
    if options.no_pickle:
        print "\n".join(["%s: %s" % (r.reviewer_username,
                                     r.summary)
                         for r in piston_reviews])
    else:
        # print to stdout where its consumed by the parent
        print pickle.dumps(piston_reviews)


