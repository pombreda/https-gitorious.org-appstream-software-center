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
        plugins = pm.get_plugins()
        self.assertEqual(len(plugins), 1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
