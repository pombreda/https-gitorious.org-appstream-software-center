#!/usr/bin/python

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
from softwarecenter.backend.piston.ureclient_pristine import (
    UbuntuRecommenderAPI)

# patch default_service_root to the one we use
from softwarecenter.enums import RECOMMENDER_HOST
UbuntuRecommenderAPI.default_service_root = RECOMMENDER_HOST+"/api/1.0"

from gettext import gettext as _

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig()

    # command line parser
    parser = argparse.ArgumentParser(description="Helper for ubuntu-recommender")
    parser.add_argument("--debug", action="store_true", default=False,
                        help="enable debug output")
    parser.add_argument("--ignore-cache", action="store_true", default=False,
                        help="force ignore cache")

    subparser = parser.add_subparsers(title="Commands")
    # recommend_top
    command = subparser.add_parser("recommend_top")
    command.set_defaults(command="recommend_top")

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    if args.ignore_cache:
        cachedir = None
    else:
        cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "uraclient")


    urclient = UbuntuRecommenderAPI(cachedir=cachedir)
        
    piston_reply = None
    kwargs = {}

    # handle the args
    if args.command == "recommend_top":
        try:
            piston_reply = urclient.recommend_top(**kwargs)
        except:
            LOG.exception("urclient_apps")
            sys.exit(1)


    if args.debug:
        LOG.debug("reply: %s" % piston_reply)
        for item in piston_reply:
            for var in vars(item):
                print "%s: %s" % (var, getattr(item, var))
            print "\n\n"


    # print to stdout where its consumed by the parent
    if piston_reply is not None:
        try:
            print pickle.dumps(piston_reply)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass
