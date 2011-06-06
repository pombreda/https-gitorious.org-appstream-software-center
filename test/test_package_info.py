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
        self.assertEqual(pkginfo.get_section('bash'), 'shells')
        self.assertEqual(pkginfo.get_summary('bash'), 'The GNU Bourne Again SHell')
        self.assertTrue(pkginfo.get_description('bash') != '')
        self.assertTrue(len(pkginfo.get_origins("firefox")) > 0)
        self.assertTrue(pkginfo.get_installed("coreutils") is not None)
        self.assertTrue(pkginfo.get_candidate("coreutils") is not None)
        self.assertTrue(len(pkginfo.get_available("coreutils")) != 0)

        self.assertTrue('coreutils' in pkginfo)
        
        pkg = pkginfo['coreutils']
        self.assertTrue(pkg is not None)
        self.assertTrue(pkg.is_installed)
        for p in ('section', 'summary', 'description', 'origins'):
            self.assertTrue(p in dir(pkg), "'%s' missing in vars()" % p)
        self.assertTrue(len(pkg.origins) != 0)
        self.assertEqual(pkg.section, "utils")
        self.assertTrue(pkg.summary != '')
        self.assertTrue(pkg.description != '')

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
