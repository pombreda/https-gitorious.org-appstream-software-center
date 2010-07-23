#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import logging
import unittest

from softwarecenter.plugin import PluginManager
from softwarecenter.utils import ExecutionTime

class MockApp(object):
    """ mock app """

class testPlugin(unittest.TestCase):

    def setUp(self):
        pass

    def test_plugin_manager(self):
        app = MockApp()
        pm = PluginManager(app, "./data/plugins")
        pm.load_plugins()
        self.assertEqual(len(pm.plugins), 1)
        self.assertTrue(pm.plugins[0].i_am_happy)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
