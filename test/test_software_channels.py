#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.backend.channel import SoftwareChannel, ChannelsManager
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *

class MockIconCache(object):
    def connect(self, signal, func):
        return True
    def load_icon(self, name, size, flags):
        return None
    def lookup_icon(self, name, size, flags):
        return None

class testSoftwareChannels(unittest.TestCase):

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.mock_icons = MockIconCache()

    def test_channels(self):
        cm = ChannelsManager(self.db, self.mock_icons)
        self.assertTrue(len(cm.channels) > 0)
        
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
