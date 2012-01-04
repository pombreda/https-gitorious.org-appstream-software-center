from piston_mini_client import (PistonAPI, PistonResponseObject,
    returns_list_of, returns_json)
from piston_mini_client.validators import (validate_pattern, validate,
    oauth_protected)

# These are factored out as constants for if you need to work against a
# server that doesn't support both schemes (like http-only dev servers)
PUBLIC_API_SCHEME = 'http'
AUTHENTICATED_API_SCHEME = 'https'

class UbuntuRecommenderAPI(PistonAPI):
    default_service_root = 'http://localhost:8000/api/2.0'

    @returns_json
    def server_status(self):
        return self._get('server-status', scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    @returns_json
    def profile(self):
        return self._get('profile', scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    def recommend_me(self):
        return self._get('recommended_me', scheme=PUBLIC_API_SCHEME)

    @oauth_protected
    @validate('pkgname', str)
    def recommend_app(self, pkgname):
        return self._get('recommended_app/%s/' % pkgname, 
                         scheme=PUBLIC_API_SCHEME)

    @returns_json
    def recommend_top(self):
        return self._get('recommend_top', scheme=PUBLIC_API_SCHEME)

    @returns_json
    def feedback(self):
        return self._get('feedback', scheme=PUBLIC_API_SCHEME)


