#!/usr/bin/python

"""
Expunge httplib2 caches
"""

import argparse
import logging
import os
import time
import sys

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='clean software-center httplib2 cache')
    parser.add_argument(
        '--debug', action="store_true",
        help='show debug output')
    parser.add_argument(
        '--dry-run', action="store_true",
        help='do not act, just show what would be done')
    parser.add_argument(
        'directories', metavar='directory', nargs='+', type=str,
        help='directories to be checked')
    parser.add_argument(
        '--by-days', type=int, default=0,
        help='expire everything older than N days')
    parser.add_argument(
        '--by-unsuccessful-http-states', action="store_true",
        help='expire any non 200 status responses')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # the time to keep stuff in the cache
    KEEP_TIME = 60*60*24* args.by_days

    if KEEP_TIME == 0 and not args.by_unsuccessful_http_states:
        print "Need either --by-days or --by-unsuccessful-http-states argument"
        sys.exit(1)

    # go over the directories
    now = time.time()
    for d in args.directories:
        for root, dirs, files in os.walk(d):
            for f in files:
                needs_rm = False
                header = open(os.path.join(root, f)).readline().strip()
                if not header.startswith("status:"):
                    logging.debug(
                        "Skipping files with unknown header: '%s'" % f)
                    continue
                if (args.by_unsuccessful_http_states and
                    header != "status: 200"):
                    needs_rm = True
                if (KEEP_TIME and
                    os.path.getmtime(os.path.join(root, f)) + KEEP_TIME < now):
                    needs_rm = true
                if needs_rm:
                    if args.dry_run:
                        print "Would delete: %s" % f
                    else:
                        logging.debug("Deleting: %s" % f)
                        os.unlink(os.path.join(root,f))
