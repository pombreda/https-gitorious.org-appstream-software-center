#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import logging
import unittest

from softwarecenter.db.pkginfo import get_pkg_info

class TestPkgInfo(unittest.TestCase):

    def setUp(self):
        pass

    def test_pkg_info(self):
        pkginfo = get_pkg_info()
        pkginfo.open()
        self.assertTrue(pkginfo.is_installed("coreutils"))
        self.assertTrue(pkginfo.is_available("bash"))
        self.assertTrue(len(pkginfo.get_addons("firefox")) > 0)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
