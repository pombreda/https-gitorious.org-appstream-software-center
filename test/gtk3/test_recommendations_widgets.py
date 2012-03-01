#!/usr/bin/python

from gi.repository import Gtk, GdkPixbuf, GObject
import os
import unittest
from gettext import gettext as _

from mock import Mock, patch

from testutils import setup_test_env, do_events
setup_test_env()
from softwarecenter.ui.gtk3.widgets.reviews import get_test_reviews_window

from softwarecenter.ui.gtk3.widgets.labels import (
    HardwareRequirementsLabel, HardwareRequirementsBox)


# window destory timeout
TIMEOUT=100

class TestRecommendationsWidgets(unittest.TestCase):

    def test_recommendations_widgets(self):
        from softwarecenter.ui.gtk3.widgets.recommendations import get_test_window
        win = get_test_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()



if __name__ == "__main__":
    import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
