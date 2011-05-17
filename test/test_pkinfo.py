#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import logging
import unittest

from softwarecenter.backend.pkginfo import get_pkginfo
from softwarecenter.utils import ExecutionTime

class TestPkgInfo(unittest.TestCase):

    def setUp(self):
        pass

    def test_pkg_info(self):
        pkginfo = get_pkginfo()
        self.assertTrue(pkginfo.is_installed("coreutils"))
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
