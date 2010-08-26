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
        self.assertEqual(res, ([], ["apt-doc", "wajig"]))
        # synaptic
        res = self.cache.get_addons("synaptic")
        # FIXME: kdebase?!?!?! that is rather unneeded
        self.assertEqual(res, (["kdebase-bin"], 
                               ["dwww", "deborphan", "menu"]))


    def test_enhances(self):
        res = self.cache.get_addons("gwenview")
        self.assertEqual(res, ([], ["kipi-plugins"]))
        

    def test_lonley_dependency(self):
        # gets additional recommends via lonely dependency
        # for arduino-core, there is a dependency on avrdude, nothing
        # else depends on avrdude other than arduino-core, so
        # we want to get the recommends/suggests/enhances for
        # this package too
        # FIXME: why only for "lonley" dependencies and not all?
        res = self.cache.get_addons("arduino-core")
        self.assertEqual(res, ([], ["avrdude-doc"]))

        

if __name__ == "__main__":
    import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
