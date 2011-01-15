# Copyright (C) 2010 Canonical
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
#
#
# taken from lp:~rnr-developers/rnr-server/rnrclient and put into
# rnrclient_pristine.py

import logging
import os
import sys

# useful for debugging
if "SOFTWARE_CENTER_DEBUG_HTTP" in os.environ:
    import httplib2
    httplib2.debuglevel = 1

# get the server to use
from softwarecenter.distro import get_distro
distro = get_distro()
SERVER_ROOT=distro.REVIEWS_SERVER

# patch default_service_root
try:
    from rnrclient_pristine import RatingsAndReviewsAPI, ReviewRequest, ReviewDetails
    RatingsAndReviewsAPI.default_service_root = SERVER_ROOT
except:
    logging.error("need python-piston-mini client\n"
                  "available in natty or from:\n"
                  "   ppa:software-store-developers/daily-build ")
    sys.exit(1)

if __name__ == "__main__":
    rnr = RatingsAndReviewsAPI()
    print rnr.server_status()
    for stat in rnr.review_stats():
        print "stats for (pkg='%s', app: '%s'):  avg=%s total=%s" % (
            stat.package_name, stat.app_name, stat.ratings_average, stat.ratings_total)
    reviews= rnr.get_reviews(language="en",origin="ubuntu",distroseries="maverick",
                             packagename="unace", appname="ACE")
    print reviews
    print rnr.get_reviews(language="en",origin="ubuntu",distroseries="natty",
                          packagename="aclock.app")
    print rnr.get_reviews(language="en", origin="ubuntu", distroseries="natty",
                          packagename="unace", appname="ACE")
