#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import gtk
import logging
import shutil
import time
import unittest

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.backend.channel import SoftwareChannel, ChannelsManager
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *
from softwarecenter.utils import ExecutionTime

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
        # wait for the cache
        while not self.db._aptcache._ready:
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.01)

    def test_channels(self):
        cm = ChannelsManager(self.db, self.mock_icons)
        # ensure we have channels
        self.assertTrue(len(cm.channels) > 0)
        # ensure we don't have any channel updates yet
        self.assertFalse(cm._check_for_channel_updates())
        # monkey patch to simulate we a empty channel list
        cm._get_channels = lambda: []
        self.assertTrue(cm._check_for_channel_updates())

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
