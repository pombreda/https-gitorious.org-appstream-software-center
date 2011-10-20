#!/usr/bin/python

import os
import sys
import unittest
sys.path.insert(0,"../")

from gi.repository import GObject

class TestNetstatus(unittest.TestCase):
    """ tests the netstaus utils """

    def test_netstaus(self):
        from softwarecenter.netstatus import get_network_watcher
        watcher = get_network_watcher()
        # FIXME: do something with the watcher
        
    def test_testping(self):
        from softwarecenter.netstatus import test_ping
        res = test_ping()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
