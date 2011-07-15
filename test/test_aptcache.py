#!/usr/bin/python

from gi.repository import GObject

import sys
sys.path.insert(0,"../")

import apt
import logging
import time
import unittest

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import ExecutionTime

class testAptCache(unittest.TestCase):

    def test_open_aptcache(self):
        # mvo: for the performance, its critical to have a 
        #      /var/cache/apt/srcpkgcache.bin - otherwise stuff will get slow

        # open s-c aptcache
        with ExecutionTime("s-c softwarecenter.apt.AptCache"):
            self.sccache = get_pkg_info()
        # cache is opened with a timeout_add() in get_pkg_info()
        time.sleep(0.2)
        context = GObject.main_context_default()
        while context.pending():
            context.iteration()
        # compare with plain apt
        with ExecutionTime("plain apt: apt.Cache()"):
            self.cache = apt.Cache()
        with ExecutionTime("plain apt: apt.Cache(memonly=True)"):
            self.cache = apt.Cache(memonly=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
