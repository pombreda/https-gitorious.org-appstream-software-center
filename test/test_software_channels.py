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
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        self.mock_icons = MockIconCache()
        # wait for the cache
        while not self.db._aptcache._ready:
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.01)
        # data
        self.repo_from_lp = "deb https://user:pw@private-ppa.launchpad.net/user/private-test/ubuntu lucid main"

    def test_channels(self):
        cm = ChannelsManager(self.db, self.mock_icons)
        # ensure we have channels
        self.assertTrue(len(cm.channels) > 0)
        # ensure we don't have any channel updates yet
        # FIXME: disabled for now as it
        #self.assertFalse(cm._check_for_channel_updates())
        # monkey patch to simulate we a empty channel list
        cm._get_channels = lambda: []
        self.assertTrue(cm._check_for_channel_updates())

    def test_channels_from_lp(self):
        cm = ChannelsManager(self.db, self.mock_icons)
        len_now = len(cm.channels)
        cm._feed_in_private_sources_list_entry(self.repo_from_lp)
        self.assertEqual(len(cm.channels), len_now + 1)

    def test_human_readable_name(self):
        from softwarecenter.utils import human_readable_name_from_ppa_uri
        from aptsources.sourceslist import SourceEntry
        se = SourceEntry(self.repo_from_lp)
        self.assertEqual(human_readable_name_from_ppa_uri(se.uri), 
                         "/user/private-test")

    def test_ppa_sources_name(self):
        from softwarecenter.utils import sources_filename_from_ppa_entry
        from aptsources.sourceslist import SourceEntry
        se = SourceEntry(self.repo_from_lp)
        self.assertEqual(sources_filename_from_ppa_entry(se),
                         "private-ppa.launchpad.net_user_private-test_ubuntu.list")
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
