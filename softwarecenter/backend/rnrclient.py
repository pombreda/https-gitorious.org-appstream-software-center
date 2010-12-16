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
# taken from lp:~rnr-developers/rnr-server/rnrclient

from urllib import quote_plus
from piston_mini_client import (PistonAPI, PistonResponseObject,
    PistonSerializable, returns_json, returns_list_of)
from piston_mini_client.validators import validate_pattern, validate

# get the server to use
from softwarecenter.distro import get_distro
distro = get_distro()
SERVER_ROOT=distro.REVIEWS_SERVER

# patch default_service_root
from rnrclient_pristine import RatingsAndReviewsAPI
RatingsAndReviewsAPI.default_service_root = SERVER_ROOT+'/reviews/api/1.0'


if __name__ == "__main__":
    rnr = RatingsAndReviewsAPI()
    print rnr.server_status()
    for stat in rnr.review_stats():
        print "stats for (pkg='%s', app: '%s'):  avg=%s total=%s" % (
            stat.package_name, stat.app_name, stat.ratings_average, stat.ratings_total)
    print rnr.get_reviews(language="en",origin="ubuntu",distroseries="natty",
                          packagename="2vcard")
    #print rnr.get_reviews(language="en",origin="ubuntu",distroseries="natty",
    #                      packagename="aclock.app")
    # FIXME: not working yet
    print rnr.get_reviews(language="en", origin="ubuntu", distroseries="natty",
                          packagename="unace", appname="ACE")
