#!/usr/bin/python

import os
import pickle
import logging
import glib
import argparse

import piston_mini_client.auth

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.scaclient import SoftwareCenterAgentAPI
from softwarecenter.backend.login_sso import get_sso_backend

from gettext import gettext as _

LOG = logging.getLogger(__name__)

class SSOLoginHelper(object):
    def __init__(self):
        self.oauth = None
        self.loop = glib.MainLoop(glib.main_context_default())
    
    def _login_successful(self, sso_backend, oauth_result):
        self.oauth = oauth_result
        # FIXME: actually verify the token against ubuntu SSO
        self.loop.quit()

    def get_oauth_token_sync(self):
        # FIXME: support xid passing for the login stuff
        xid = 0
        sso = get_sso_backend(
            xid, "Ubuntu Software Center Store",
            _("To reinstall previous purchases, sign in to the "
              "Ubuntu Single Sign-On account you used to pay for them."))
        
        sso.connect("login-successful", self._login_successful)
        sso.connect("login-failed", lambda s: self.loop.quit())
        sso.connect("login-canceled", lambda s: self.loop.quit())
        sso.login_or_register()
        self.loop.run()
        return self.oauth

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(description="Helper for software-center-agent")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
    parser.add_argument("--ignore-cache", action="store_true", default=False,
                        help="force ignore cache")
    subparser = parser.add_subparsers(title="Commands")
    # available_apps
    command = subparser.add_parser("available_apps")
    command.add_argument("lang")
    command.add_argument("series")
    command.add_argument("arch")
    command.set_defaults(command="available_apps")

    # available_apps_qa
    command = subparser.add_parser("available_apps_qa")
    command.add_argument("lang")
    command.add_argument("series")
    command.add_argument("arch")
    command.set_defaults(command="available_apps_qa")
    # subscriptions
    command = subparser.add_parser("subscriptions_for_me")
    command.set_defaults(command="subscriptions_for_me")

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "scaclient")


    # check if auth is required
    if args.command in ("available_apps_qa", "subscriptions_for_me"):
        token = SSOLoginHelper().get_oauth_token_sync()
        auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                       token["token_secret"],
                                                       token["consumer_key"],
                                                       token["consumer_secret"])
        scaclient = SoftwareCenterAgentAPI(cachedir=cachedir, auth=auth)
    else:
        scaclient = SoftwareCenterAgentAPI(cachedir=cachedir)
        
    piston_reply = None

    # common kwargs
    if args.command in ("available_apps", "available_apps_qa"):
        kwargs = {"lang": args.lang,
                  "series": args.series,
                  "arch": args.arch
                  }

    # handle the args
    if args.command == "available_apps":
        try:
            piston_reply = scaclient.available_apps(**kwargs)
        except:
            LOG.exception("available_apps")
    elif args.command == "available_apps_qa":
        try:
            piston_reply = scaclient.available_apps_qa(**kwargs)
        except:
            LOG.exception("available_apps_qa")
    elif args.command == "subscriptions_for_me":
        try:
            piston_reply = scaclient.subscriptions_for_me()
        except:
            LOG.exception("subscriptions_for_me")

    # print to stdout where its consumed by the parent
    if piston_reply is not None:
        try:
            print pickle.dumps(piston_reply)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass
