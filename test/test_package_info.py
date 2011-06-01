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
        self.assertTrue(len(pkginfo.get_versions("coreutils")) != 0)

        self.assertTrue('coreutils' in pkginfo)
        
        pkg = pkginfo['coreutils']
        self.assertTrue(pkg is not None)
        self.assertTrue(pkg.is_installed)
        self.assertTrue(len(pkg.origins) != 0)
        self.assertTrue(len(pkg.versions) != 0)
        self.assertEqual(pkg.section, "utils")
        self.assertNotEqual(pkg.summary, '')
        self.assertNotEqual(pkg.description, '')
        self.assertEqual(pkg.website, 'http://gnu.org/software/coreutils')
        self.assertNotEqual(pkg.size, 0)
        self.assertNotEqual(pkg.installed_size, 0)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
