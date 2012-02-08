#!/usr/bin/python

from gi.repository import Gtk, GObject
import unittest

from testutils import setup_test_env
setup_test_env()

TIMEOUT=300

class TestRecommendationsPanel(unittest.TestCase):

    def test_recommendations_panel(self):
        from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()


    def _p(self):
        while Gtk.events_pending():
            Gtk.main_iteration()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
