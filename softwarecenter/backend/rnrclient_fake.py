"""This module provides the RatingsAndReviewsAPI class for talking to the
ratings and reviews API, plus a few helper classes.
"""

from urllib import quote_plus
from piston_mini_client import (
    PistonAPI,
    PistonResponseObject,
    PistonSerializable,
    returns,
    returns_json,
    returns_list_of,
    )
from piston_mini_client.validators import validate_pattern, validate
from piston_mini_client.failhandlers import APIError

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'

from rnrclient_pristine import ReviewRequest, ReviewsStats, ReviewDetails
from test.fake_review_settings import FakeReviewSettings
import piston_mini_client
import simplejson
import random
import time

class RatingsAndReviewsAPI(PistonAPI):
    """A fake client pretending to be RAtingsAndReviewsAPI from rnrclient_pristine.
       Uses settings from the class in test.fake_review_settings. FakeReviewSettings
       to provide predictable responses to methods that try to use the 
       RatingsAndReviewsAPI for testing purposes (i.e. without network activity).
       To use this, instead of importing from rnrclient_pristine, you can import
       from rnrclient_fake instead.
    """
    
    default_service_root = 'http://localhost:8000/reviews/api/1.0'
    default_content_type = 'application/x-www-form-urlencoded'
    exception_msg = 'Fake RatingsAndReviewsAPI raising fake exception'

    @returns_json
    def server_status(self):
        if FakeReviewSettings.server_response_ok:
            return simplejson.dumps('ok')
        else:
            raise APIError(self.exception_msg)


    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate('days', int, required=False)
    @returns_list_of(ReviewsStats)
    def review_stats(self, origin='any', distroseries='any', days=None,
        valid_days=(1,3,7)):
        """Fetch ratings for a particular distroseries"""
        url = 'review-stats/{0}/{1}/'.format(origin, distroseries)
        if days is not None:
            # the server only knows valid_days (1,3,7) currently
            for valid_day in valid_days:
                # pick the day from valid_days that is the next bigger than
                # days
                if days <= valid_day:
                    url += 'updates-last-{0}-days/'.format(valid_day)
                    break
        #return self._get(url, scheme=PUBLIC_API_SCHEME)

    @validate_pattern('language', r'\w+', required=False)
    @validate_pattern('origin', r'[0-9a-z+-.:/]+', required=False)
    @validate_pattern('distroseries', r'\w+', required=False)
    @validate_pattern('version', r'[-\w+.:~]+', required=False)
    @validate_pattern('packagename', r'[a-z0-9.+-]+')
    @validate('appname', str, required=False)
    @validate('page', int, required=False)
    @returns_list_of(ReviewDetails)
    def get_reviews(self, packagename, language='any', origin='any',
        distroseries='any', version='any', appname='', page=1):
        if FakeReviewSettings.get_reviews_error:
            raise APIError(self.exception_msg)
        else:
            reviews = self._make_fake_reviews(packagename, 
                                              FakeReviewSettings.reviews_returned)
            return simplejson.dumps(reviews)

    @validate('review_id', int)
    @returns(ReviewDetails)
    def get_review(self, review_id):
        if FakeReviewSettings.get_review_error:
            raise APIError(self.exception_msg)
        else:
            review = self._make_fake_reviews(single_id=review_id)
            return simplejson.dumps(review)

    @validate('review', ReviewRequest)
    @returns(ReviewDetails)
    def submit_review(self, review):
        """Submit a rating/review."""
        #return self._post('reviews/', data=review,
        #scheme=AUTHENTICATED_API_SCHEME, content_type='application/json')

    @validate('review_id', int)
    @validate_pattern('reason', r'[^\n]+')
    @validate_pattern('text', r'[^\n]+')
    @returns_json
    def flag_review(self, review_id, reason, text):
        """Flag a review as being inappropriate"""
        data = {'reason': reason,
            'text': text,
        }
        #return self._post('reviews/%s/flags/' % review_id, data=data,
        #scheme=AUTHENTICATED_API_SCHEME)

    @validate('review_id', int)
    @validate_pattern('useful', 'True|False')
    @returns_json
    def submit_usefulness(self, review_id, useful):
        """Submit a usefulness vote."""
        #return self._post('/reviews/%s/recommendations/' % review_id,
        #    data={'useful': useful}, scheme=AUTHENTICATED_API_SCHEME)

    @validate('review_id', int, required=False)
    @validate_pattern('username', r'[^\n]+', required=False)
    @returns_json
    def get_usefulness(self, review_id=None, username=None):
        """Get a list of usefulness filtered by username/review_id"""
        if not username and not review_id:
            return None

        data = {}

        if username:
            data['username'] = username
        if review_id:
            data['review_id'] = str(review_id)

        #return self._get('usefulness/', args=data,
        #    scheme=PUBLIC_API_SCHEME)
        
        
    def _make_fake_reviews(self, packagename='compiz-core', 
                           quantity=1, single_id=None):
        """Make and return a requested quantity of fake reviews"""
        USERS = ["Joe Doll", "John Foo", "Cat Lala", "Foo Grumpf", 
                 "Bar Tender", "Baz Lightyear"]
        SUMMARIES = ["Cool", "Medium", "Bad", "Too difficult"]
        TEXT = ["Review text number 1", "Review text number 2", 
                "Review text number 3", "Review text number 4"]
        
        reviews = []
        
        for i in range(0, quantity):
            if quantity == 1 and single_id:
                id = single_id
            else:
                id = 1*3
                
            r = {
                        "origin": "ubuntu",
                        "rating": random.randint(1,5),
                        "hide": False,
                        "app_name": "",
                        "language": "en",
                        "reviewer_username": random.choice(USERS),
                        "usefulness_total": random.randint(3,6),
                        "usefulness_favorable": random.randint(1,3),
                        "review_text": random.choice(TEXT),
                        "date_deleted": None,
                        "summary": random.choice(SUMMARIES),
                        "version": "1:0.9.4",
                        "id": id,
                        "date_created": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "reviewer_displayname": "Fake Person",
                        "package_name": packagename,
                        "distroseries": "natty"
            }
            reviews.append(r)
            
        #get_review wants a dict but get_reviews wants a list of dicts
        if single_id:
            return r
        else:
            return reviews
