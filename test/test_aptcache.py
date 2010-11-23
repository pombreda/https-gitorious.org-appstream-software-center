#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt
import apt_pkg
import datetime
import glib
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
        with ExecutionTime("softwarecenter.apt.AptCache"):
            self.sccache = AptCache()
        with ExecutionTime("apt.Cache()"):
            self.cache = apt.Cache()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
