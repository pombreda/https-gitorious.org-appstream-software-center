#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import gtk
import logging
import time
import unittest

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.backend.channel import AptChannelsManager, get_channels_manager, is_channel_available
from softwarecenter.db.database import StoreDatabase
from softwarecenter.paths import XAPIAN_BASE_PATH

class MockIconCache(object):
    def connect(self, signal, func):
        return True
    def load_icon(self, name, size, flags):
        return None
    def lookup_icon(self, name, size, flags):
        return None

class TestSoftwareChannels(unittest.TestCase):

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = get_pkg_info()
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()
        # wait for the cache
        while not self.db._aptcache._ready:
            while gtk.events_pending():
                gtk.main_iteration()
            time.sleep(0.01)
        # data
        self.repo_from_lp = "deb https://user:pw@private-ppa.launchpad.net/user/private-test/ubuntu lucid main"

    def test_origin(self):
        origin = self.cache.get_origin("libc6")
        self.assertEqual(origin, "ubuntu")
        
    def test_channels(self):
        cm = AptChannelsManager(self.db)
        # ensure we have channels
        self.assertTrue(len(cm.channels) > 0)
        # test channel_available
        #for c in cm.channels:
        #     self.assertTrue(cm.channel_available(c.origin))
        self.assertFalse(AptChannelsManager.channel_available('asfd12da098p'))
        self.assertFalse(is_channel_available('asfd12da098p'))
        # ensure we don't have any channel updates yet
        # FIXME: disabled for now as it
        #self.assertFalse(cm._check_for_channel_updates())
        # monkey patch to simulate we a empty channel list
        cm._get_channels = lambda: []
        self.assertTrue(cm._check_for_channel_updates())

    def test_channels_from_lp(self):
        cm = AptChannelsManager(self.db)
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
                         
    def test_obfuscate_private_ppa_details(self):
        from softwarecenter.utils import obfuscate_private_ppa_details
        text = "Failed to fetch https://kingoflimbs:R5kGP7MpK777GMiB7bFw@private-ppa.launchpad.net/commercial-ppa-uploaders/steel-storm2/ubuntu/pool/main/s/steelstorm-episode2/steelstorm-episode2-data_2.00.02797-0maverick1_all.deb SSL connection timeout at 117523"
        expected = "Failed to fetch https://hidden:hidden@private-ppa.launchpad.net/commercial-ppa-uploaders/steel-storm2/ubuntu/pool/main/s/steelstorm-episode2/steelstorm-episode2-data_2.00.02797-0maverick1_all.deb SSL connection timeout at 117523"
        result = obfuscate_private_ppa_details(text)
        self.assertEqual(result, expected)
        
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
