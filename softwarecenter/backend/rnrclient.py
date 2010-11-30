# 
# Copied from lp:~elachuni/rnr-server/rnrclient 
#

import logging
import sys

try:
    import pistonclient
except ImportError:
    logging.error("need pistonclient, see contrib/README for details")
    raise

from pistonclient import (PistonAPI, PistonResponseObject, 
                          PistonSerializable,
                          returns_json, returns_list_of)
from pistonclient.validators import validate_pattern, validate

class ReviewRequest(PistonSerializable):
    _atts = ('package_name', 'summary', 'package_version', 'review_text',
        'date', 'rating')

class ReviewsStats(PistonResponseObject):
    """This class will be populated with the retrieved JSON"""
    pass

class ReviewDetails(PistonResponseObject):
    """This class will be populated with the retrieved JSON"""
    pass

class RatingsAndReviewsAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/reviews/api/1.0'

    @returns_json
    def server_status(self):
        """Check the state of the server, to see if everything's ok."""
        return self._get('server-status')

    @validate_pattern('language', r'\w+')
    @validate_pattern('origin', r'\w+')
    @validate_pattern('distroseries', r'\w+')
    @returns_list_of(ReviewsStats)
    def review_stats(self, language, origin, distroseries):
        """Fetch ratings for a particular distroseries"""
        return self._get('%s/%s/%s/review-stats' % (language, origin,
            distroseries))

    @validate_pattern('language', r'\w+')
    @validate_pattern('origin', r'\w+')
    @validate_pattern('distroseries', r'\w+')
    @validate_pattern('packagename', r'[\w-]+')
    @validate_pattern('appname', r'\w+', required=False)
    @returns_list_of(ReviewDetails)
    def get_reviews(self, language, origin, distroseries, packagename,
        appname=''):
        """Fetch ratings and reviews for a particular package name.

        If appname is provided, fetch reviews for that particular app, not
        the whole package.
        """
        if appname:
            appname = '/' + appname
        return self._get('%s/%s/%s/binary/%s%s' % (language, origin,
            distroseries, packagename, appname))

    @validate_pattern('language', r'\w+')
    @validate_pattern('origin', r'\w+')
    @validate_pattern('distroseries', r'\w+')
    @validate('review', ReviewRequest)
    @returns_json
    def submit_review(self, language, origin, distroseries, review):
        """Submit a rating/review."""
        return self._post('%s/%s/%s/create', data=review,
            content_type='application/json')

    @validate('review_id', int)
    @validate_pattern('reason', r'[^\n]+')
    @validate_pattern('text', r'[^\n]+')
    def report_abuse(self, review_id, reason, text):
        """Flag a review as being inappropriate"""
        data = {'reason':reason,
            'text': text,
        }
        return self._post('%s/report-review' % review_id, data=data),

if __name__ == "__main__":
    rnr = RatingsAndReviewsAPI()
    print rnr.server_status()
