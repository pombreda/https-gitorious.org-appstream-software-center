#!/usr/bin/python

from gi.repository import GObject
#from mock import patch
import unittest

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
        recommender_agent = RecommenderAgent()
        recommender_agent.connect("recommend-top", self.on_query_done)
        recommender_agent.connect("error", self.on_query_error)
        recommender_agent.query_recommend_top()
        self.loop.run()
        self.assertFalse(self.error)

#    def test_recagent_query_recommend_top_uses_complete_only(self):
#        run_generic_piston_helper_fn = (
#            'softwarecenter.backend.spawn_helper.SpawnHelper.'
#            'run_generic_piston_helper')
#        with patch(run_generic_piston_helper_fn) as mock_run_piston_helper:
#            recommender_agent = RecommenderAgent()
#            self.recommender_agent.query_recommend_top()

#            mock_run_piston_helper.assert_called_with(
#                'RecommenderAgentAPI', 'recommend_top',
#                complete_only=True)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
