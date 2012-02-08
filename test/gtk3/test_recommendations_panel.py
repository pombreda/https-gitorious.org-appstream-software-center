#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest
from mock import patch

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestRecommendationsPanel(unittest.TestCase):

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recommends.RecommenderAgent'
           '.query_recommend_me')
    def test_recommendations_panel(self, mock_query):
        from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window_recommendations_panel
        win = get_test_window_recommendations_panel()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        
    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
