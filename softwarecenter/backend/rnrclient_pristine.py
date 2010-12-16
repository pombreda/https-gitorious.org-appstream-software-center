from urllib import quote_plus
from piston_mini_client import (PistonAPI, PistonResponseObject,
    PistonSerializable, returns_json, returns_list_of)
from piston_mini_client.validators import validate_pattern, validate


class ReviewRequest(PistonSerializable):
    _atts = ('package_name', 'summary', 'version', 'review_text',
        'rating', 'language', 'origin', 'distroseries', 'arch_tag')

class ReviewsStats(PistonResponseObject):
    """This class will be populated with the retrieved JSON"""
    pass


class ReviewDetails(PistonResponseObject):
    """This class will be populated with the retrieved JSON"""
    pass


class RatingsAndReviewsAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/reviews/api/1.0'
    default_content_type = 'application/x-www-form-urlencoded'

    @returns_json
    def server_status(self):
        """Check the state of the server, to see if everything's ok."""
        return self._get('server-status')

    @validate('days', int, required=False)
    @returns_list_of(ReviewsStats)
    def review_stats(self, days=None):
        """Fetch ratings for a particular distroseries"""
        url = 'review-stats/'
        if days is not None:
            url += 'updates-last-{0}-days/'.format(days)
        return self._get(url)

    @validate_pattern('language', r'\w+')
    @validate_pattern('origin', r'\w+')
    @validate_pattern('distroseries', r'\w+')
    @validate_pattern('packagename', r'[\w-]+')
    @validate_pattern('appname', r'\w+', required=False)
    @validate('page', int, required=False)
    @returns_list_of(ReviewDetails)
    def get_reviews(self, language, origin, distroseries, packagename,
        appname='', page=1):
        """Fetch ratings and reviews for a particular package name.

        If appname is provided, fetch reviews for that particular app, not
        the whole package.
        """
        if appname:
            appname = quote_plus('/' + appname)
        return self._get('%s/%s/%s/%s%s/page/%s/' % (language, origin,
            distroseries, packagename, appname, page))

    @validate('review', ReviewRequest)
    @returns_json
    def submit_review(self, review):
        """Submit a rating/review."""
        return self._post('reviews/create/', data=review,
            content_type='application/json')

    @validate('review_id', int)
    @validate_pattern('reason', r'[^\n]+')
    @validate_pattern('text', r'[^\n]+')
    def report_abuse(self, review_id, reason, text):
        """Flag a review as being inappropriate"""
        data = {'reason': reason,
            'text': text,
        }
        return self._post('%s/report-review/' % review_id, data=data),

    @validate('review_id', int)
    @validate_pattern('useful', 'True|False')
    @returns_json
    def submit_usefulness(self, review_id, useful):
        """Submit a usefulness vote."""
        return self._post('/reviews/%s/usefulness/%s' % (review_id, useful),
            data={})

