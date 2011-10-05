#!/usr/bin/python

from gi.repository import GObject
import os
import os.path
import unittest


import sys
sys.path.insert(0,"../")

from softwarecenter.backend.scagent import SoftwareCenterAgent
import softwarecenter.paths

class TestSCAgent(unittest.TestCase):
    """ tests software-center-agent """

    def setUp(self):
        self.loop = GObject.MainLoop(GObject.main_context_default())
        softwarecenter.paths.datadir = "../data"
        os.environ["PYTHONPATH"] = os.path.abspath("..")
        self.error = False

    def on_query_done(self, scagent, data):
        print "query done, data: '%s'" % data
        self.loop.quit()
        
    def on_query_error(self, scagent, error):
        self.loop.quit()
        self.error = True

    def test_scagent_query_available(self):
        sca = SoftwareCenterAgent()
        sca.connect("available", self.on_query_done)
        sca.connect("error", self.on_query_error)
        sca.query_available()
        self.loop.run()        
        self.assertFalse(self.error)

    # disabled for now as this is not yet on staging or production
    def disabled_test_scagent_query_exhibits(self):
        sca = SoftwareCenterAgent()
        sca.connect("exhibits", self.on_query_done)
        sca.connect("error", self.on_query_error)
        sca.query_exhibits()
        self.loop.run()  
        self.assertFalse(self.error)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
