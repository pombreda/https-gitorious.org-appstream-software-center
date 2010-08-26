#!/usr/bin/python

import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.apt.aptcache import AptCache

class TestSCAddons(unittest.TestCase):
    """ tests the addons """

    def setUp(self):
        self.cache = AptCache()
        self.cache.open()

    def test_get_addons_simple(self):
        # 7zip
        res = self.cache.get_addons("p7zip-full")
        self.assertEqual(res, ([], ["p7zip-rar"]))
        # apt has no relevant ones
        res = self.cache.get_addons("apt")
        self.assertEqual(res, ([], []))
        self.assertTrue(res, ([], []))
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
