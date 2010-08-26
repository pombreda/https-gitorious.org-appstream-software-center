#!/usr/bin/python

import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.apt.aptcache import AptCache

class TestSCAddons(unittest.TestCase):
    """ tests the addons """

    def test_get_addons(self):
        cache = AptCache()
        cache.open()
        res = cache.get_addons("p7zip-full")
        self.assertEqual(res, ([], ["p7zip-rar"])

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
