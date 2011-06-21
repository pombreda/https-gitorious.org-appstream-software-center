#!/usr/bin/python

import os
import pickle
import logging

import argparse

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from softwarecenter.backend.scaclient import SoftwareCenterAgentAPI

LOG = logging.getLogger(__name__)

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
            LOG.exception("get_review_stats")

    # print to stdout where its consumed by the parent
    if piston_reply:
        try:
            print pickle.dumps(piston_reply)
        except IOError:
            # this can happen if the parent gets killed, no need to trigger
            # apport for this
            pass
