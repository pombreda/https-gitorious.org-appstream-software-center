#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt
import apt_pkg
import datetime
import glib
import gtk
import logging
import os
import subprocess
import time
import unittest

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.utils import ExecutionTime

class testAptCache(unittest.TestCase):

    def setUp(self):
        rundir = os.path.abspath(os.path.dirname(sys.argv[0]))

    def test_open_aptcache(self):
        # mvo: for the performance, its critical to have a 
        #      /var/cache/apt/srcpkgcache.bin - otherwise stuff will get slow

        # open s-c aptcache
        with ExecutionTime("s-c softwarecenter.apt.AptCache"):
            self.sccache = AptCache()
        # cache is opened with a timeout_add() in AptCache()
        time.sleep(0.2)
        while gtk.events_pending():
            gtk.main_iteration()
        # compare with plain apt
        with ExecutionTime("plain apt: apt.Cache()"):
            self.cache = apt.Cache()
        with ExecutionTime("plain apt: apt.Cache(memonly=True)"):
            self.cache = apt.Cache(memonly=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
