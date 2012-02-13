#!/usr/bin/python

from gi.repository import GObject
import unittest
import os

from testutils import setup_test_env
setup_test_env()

from softwarecenter.backend.recagent import RecommenderAgent

from softwarecenter.utils import get_uuid
recommender_uuid = get_uuid()

class TestRecommenderAgent(unittest.TestCase):
    """ tests the recommender agent """

    def setUp(self):
        self.loop = GObject.MainLoop(GObject.main_context_default())
        self.error = False

    def on_query_done(self, recagent, data):
        print "query done, data: '%s'" % data
        self.loop.quit()
        
    def on_query_error(self, recagent, error):
        print "query error received: ", error
        self.loop.quit()
        self.error = True
        
    def test_recagent_query_server_status(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("server-status", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_server_status()
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_submit_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("submit-profile", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_submit_profile(data=["pitivi", "fretsonfire"])
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_submit_anon_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("submit-anon-profile", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_submit_anon_profile(
                uuid=recommender_uuid,
                installed_packages=["pitivi", "fretsonfire"],
                extra="")
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def disabled_test_recagent_query_profile(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("profile", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_profile(pkgnames=["pitivi", "fretsonfire"])
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]

    def disabled_test_recagent_query_recommend_me(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-me", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_me()
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_recommend_app(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-app", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_app("pitivi")
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_recommend_all_apps(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-all-apps", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_all_apps()
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_recommend_top(self):
        # NOTE: This requires a working recommender host that is reachable
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://rec.staging.ubuntu.com"
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertFalse(self.error)
        del os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"]
        
    def test_recagent_query_error(self):
        # forces an error 'cuz there definitely ain't a server here!!
        os.environ["SOFTWARE_CENTER_RECOMMENDER_HOST"] = "https://orange.staging.ubuntu.com"
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
