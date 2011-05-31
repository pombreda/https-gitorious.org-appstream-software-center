from piston_mini_client import (PistonAPI, PistonResponseObject,
    returns_list_of, returns_json)
from piston_mini_client.validators import (validate_pattern, validate,
    oauth_protected)


class SoftwareCenterAgentAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/api/2.0'

    @validate_pattern('lang', r'[^/]{1,9}$')
    @validate_pattern('series', r'[^/]{1,20}$')
    @validate_pattern('arch', r'[^/]{1,10}$')
    @returns_list_of(PistonResponseObject)
    def available_apps(self, lang, series, arch):
        """Retrieve the list of currently available apps for purchase."""
        return self._get(
            'applications/%s/ubuntu/%s/%s/' % (lang, series, arch))

    @validate_pattern('lang', r'[^/]{1,9}$')
    @validate_pattern('series', r'[^/]{1,20}$')
    @validate_pattern('arch', r'[^/]{1,10}$')
    @oauth_protected
    @returns_list_of(PistonResponseObject)
    def available_apps_qa(self, lang, series, arch):
        """Retrieve the list of currently available apps for purchase."""
        return self._get(
            'applications_qa/%s/ubuntu/%s/%s/' % (lang, series, arch))

    @oauth_protected
    @validate('complete_only', bool, required=False)
    @returns_list_of(PistonResponseObject)
    def subscriptions_for_me(self, complete_only=False):
        return self._get('subscriptions/',
            args={'complete_only': complete_only})

    @oauth_protected
    @validate('id', int)
    @returns_json
    def subscription_by_id(self, id=None):
        return self._get('subscription/%d' % (id))
