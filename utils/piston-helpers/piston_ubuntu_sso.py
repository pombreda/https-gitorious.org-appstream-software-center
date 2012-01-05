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
from piston_get_scagent_available_apps import SSOLoginHelper

# patch default_service_root to the one we use
from softwarecenter.enums import SSO_LOGIN_HOST
UbuntuSsoAPI.default_service_root = SSO_LOGIN_HOST+"/api/1.0"

from gettext import gettext as _

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(description="Helper for recommender-api")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
    parser.add_argument("--ignore-cache", action="store_true", default=False,
                        help="force ignore cache")
    parser.add_argument("--parent-xid", default=0,
                        help="xid of the parent window")

    subparser = parser.add_subparsers(title="Commands")
    # recommend_top
    command = subparser.add_parser("whoami")
    command.set_defaults(command="whoami")

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "uraclient")

    # all calls are authenticated
    helper = SSOLoginHelper(args.parent_xid)
    token = helper.get_oauth_token_sync()

    auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                   token["token_secret"],
                                                   token["consumer_key"],
                                                   token["consumer_secret"])
    urclient = UbuntuSsoAPI(cachedir=cachedir, auth=auth)
        
    piston_reply = None
    # handle the args
    f = getattr(urclient, args.command)
    try:
        piston_reply = f()
    except:
        LOG.exception("urclient_apps")
        sys.exit(1)

    # print to stdout where its consumed by the parent
    if piston_reply is not None:
        try:
            print pickle.dumps(piston_reply)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass
