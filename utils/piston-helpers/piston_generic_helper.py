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

from gi.repository import GObject

import argparse
import logging
import os
import json
import pickle
import sys

# useful for debugging
if "SOFTWARE_CENTER_DEBUG_HTTP" in os.environ:
    import httplib2
    httplib2.debuglevel = 1

import piston_mini_client.auth

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.piston.ubuntusso_pristine import (
    UbuntuSsoAPI)
from softwarecenter.backend.piston.rnrclient import RatingsAndReviewsAPI

from piston_get_scagent_available_apps import SSOLoginHelper

# patch default_service_root to the one we use
from softwarecenter.enums import SSO_LOGIN_HOST
UbuntuSsoAPI.default_service_root = SSO_LOGIN_HOST+"/api/1.0"

from gettext import gettext as _

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(
        description="Backend helper for piston-mini-client based APIs")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
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
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "uraclient")
        
    # check what we need to call
    klass = globals()[args.klass]
    func = args.function
    kwargs = json.loads(args.kwargs)

    if args.needs_auth:
        helper = SSOLoginHelper(args.parent_xid)
        token = helper.get_oauth_token_sync()
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
