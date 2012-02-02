#!/usr/bin/python

from gi.repository import GObject
import unittest
import os

from testutils import setup_test_env
setup_test_env()

from softwarecenter.backend.recommends import RecommenderAgent

class TestRecommenderAgent(unittest.TestCase):
    """ tests the recommender agent """

    def setUp(self):
        self.loop = GObject.MainLoop(GObject.main_context_default())
        self.error = False

    def on_query_done(self, recagent, data):
        print "query done, data: '%s'" % data
        self.loop.quit()
        
    def on_query_error(self, recagent, error):
        self.loop.quit()
        self.error = True
        
    def test_recagent_query_recommend_top(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com/"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
#    def test_recagent_query_recommend_me(self):
#        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com/"
#        recommender_agent = RecommenderAgent()
#        recommender_agent.connect("recommend-me", self.on_query_done)
#        recommender_agent.connect("error", self.on_query_error)
#        recommender_agent.query_recommend_me()
#        self.loop.run()
#        self.assertFalse(self.error)
#        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_error(self):
        # there definitely ain't no server here
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://orange.staging.ubuntu.com/"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertTrue(self.error)
        
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
