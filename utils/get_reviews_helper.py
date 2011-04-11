#!/usr/bin/python

import pickle
import sys
import logging

from softwarecenter.paths import *
from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI, ReviewDetails

LOG = logging.getLogger(__name__)

if __name__ == "__main__":

    language = sys.argv[1]
    origin = sys.argv[2]
    distroseries = sys.argv[3]
    pkgname = sys.argv[4]
    
    cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "rnrclient")
    rnrclient = RatingsAndReviewsAPI(cachedir=cachedir)

    kwargs = {"language": language, 
              "origin": origin,
              "distroseries": distroseries,
              "packagename": pkgname,
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


