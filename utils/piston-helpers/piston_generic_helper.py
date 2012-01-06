#!/usr/bin/python
# Copyright (C) 2011 Canonical
#
# Authors:
#  Michael Vogt
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

import argparse
import logging
import os
import json
import pickle
import sys

from gi.repository import GObject

# useful for debugging
if "SOFTWARE_CENTER_DEBUG_HTTP" in os.environ:
    import httplib2
    httplib2.debuglevel = 1

import piston_mini_client.auth

try:
    import softwarecenter
except ImportError:
    if os.path.exists("../softwarecenter"):
        sys.path.insert(0, "../")
    else:
        sys.path.insert(0, "/usr/share/software-center")

import softwarecenter.paths
from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.login_sso import get_sso_backend

from softwarecenter.enums import (SOFTWARE_CENTER_NAME_KEYRING,
                                  SOFTWARE_CENTER_SSO_DESCRIPTION,
                                  )
                                  
from softwarecenter.utils import clear_token_from_ubuntu_sso

# the piston import
from softwarecenter.backend.piston.ubuntusso_pristine import UbuntuSsoAPI
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI
from softwarecenter.backend.piston.scaclient import SoftwareCenterAgentAPI

RatingsAndReviewsAPI # pyflakes
UbuntuSsoAPI # pyflakes
SoftwareCenterAgentAPI # pyflakes

# patch default_service_root to the one we use
from softwarecenter.enums import SSO_LOGIN_HOST
UbuntuSsoAPI.default_service_root = SSO_LOGIN_HOST+"/api/1.0"

from gettext import gettext as _

# helper that is only used to verify that the token is ok
# and trigger cleanup if not
class SSOLoginHelper(object):

    def __init__(self, xid=0):
        self.oauth = None
        self.xid = xid
        self.loop = GObject.MainLoop(GObject.main_context_default())
    
    def _login_successful(self, sso_backend, oauth_result):
        LOG.debug("_login_successful")
        self.oauth = oauth_result
        # FIXME: actually verify the token against ubuntu SSO
        self.loop.quit()

    def verify_token_sync(self, token):
        LOG.debug("verify_token")
        auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                       token["token_secret"],
                                                       token["consumer_key"],
                                                       token["consumer_secret"])
        api = UbuntuSsoAPI(auth=auth)
        try:
            res = api.whoami()
        except:
            LOG.exception("api.whoami failed")
            return None
        return res

    def clear_token(self):
        clear_token_from_ubuntu_sso(SOFTWARE_CENTER_NAME_KEYRING)

    def get_oauth_token_sync(self):
        self.oauth = None
        sso = get_sso_backend(
            self.xid, 
            SOFTWARE_CENTER_NAME_KEYRING,
            _(SOFTWARE_CENTER_SSO_DESCRIPTION))
        sso.connect("login-successful", self._login_successful)
        sso.connect("login-failed", lambda s: self.loop.quit())
        sso.connect("login-canceled", lambda s: self.loop.quit())
        sso.login_or_register()
        self.loop.run()
        return self.oauth

    def get_oauth_token_and_verify_sync(self):
        token = self.get_oauth_token_sync()
        # check if the token is valid and reset it if it is not
        if token and not self.verify_token_sync(token):
            self.clear_token()
            # re-trigger login
            token = self.get_oauth_token_sync()
        return token



LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(
        description="Backend helper for piston-mini-client based APIs")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
    parser.add_argument("--datadir", default="/usr/share/software-center",
                        help="setup alternative datadir")
    parser.add_argument("--ignore-cache", action="store_true", default=False,
                        help="force ignore cache")
    parser.add_argument("--needs-auth", default=False, action="store_true",
                        help="need oauth credentials")
    parser.add_argument("--output", default="pickle",
                        help="output result as [pickle|json|text]")
    parser.add_argument("--parent-xid", default=0,
                        help="xid of the parent window")
    parser.add_argument('klass', help='class to use')
    parser.add_argument('function', help='function to call')
    parser.add_argument('kwargs', nargs="?",
                        help='kwargs for the function call as json')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "piston-helper")
        
    # check what we need to call
    klass = globals()[args.klass]
    func = args.function
    kwargs = json.loads(args.kwargs or '{}')

    softwarecenter.paths.datadir = args.datadir

    if args.needs_auth:
        helper = SSOLoginHelper(args.parent_xid)
        token = helper.get_oauth_token_and_verify_sync()
        # if we don't have a token, error here
        if not token:
            sys.stderr.write("ERROR: can not obtain a oauth token\n")
            sys.exit(1)

        auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                       token["token_secret"],
                                                       token["consumer_key"],
                                                       token["consumer_secret"])
        api = klass(cachedir=cachedir, auth=auth)
    else:
        api = klass()
        
    piston_reply = None
    # handle the args
    f = getattr(api, func)
    try:
        piston_reply = f(**kwargs)
    except:
        LOG.exception("urclient_apps")
        sys.exit(1)

    # print to stdout where its consumed by the parent
    if piston_reply is None:
        LOG.warn("no data")
        sys.exit(0)

    # check what format to use
    if args.output == "pickle":
        res = pickle.dumps(piston_reply)
    elif args.output == "json":
        res = json.dumps(piston_reply)
    elif args.output == "text":
        res = piston_reply

    # and output it
    try:
        print res
    except IOError:
        # this can happen if the parent gets killed, no need to trigger
        # apport for this
        pass
