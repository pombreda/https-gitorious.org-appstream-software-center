#!/usr/bin/python

from gi.repository import GObject

import apt
import logging
import time
import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import ExecutionTime

class TestAptCache(unittest.TestCase):

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

    def test_get_total_size(self):
        cache = get_pkg_info()
        pkgname = "software-center"
        addons_to_install = addons_to_remove = []
        archive_suite = ""
        cache.get_total_size_on_install(
            pkgname, addons_to_install, addons_to_remove, archive_suite)
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
