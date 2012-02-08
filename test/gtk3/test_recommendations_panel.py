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
    def test_recommendations_panel_is_displayed(self, mock_query):
        from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window_recommendations_panel
        win = get_test_window_recommendations_panel()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        
    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recommends.RecommenderAgent'
           '.query_recommend_me')
    def test_recommendations_panel_spinner_view(self, mock_query):
        from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window_recommendations_panel
        from softwarecenter.ui.gtk3.widgets.containers import FramedHeaderBox
        win = get_test_window_recommendations_panel()
        rec_panel = win.get_data("rec_panel")
        self._p()
        self.assertTrue(rec_panel.recommended_for_you_frame.spinner_notebook.get_current_page() == FramedHeaderBox.SPINNER)
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()
        
    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
