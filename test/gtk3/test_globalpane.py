#!/usr/bin/python

import sys
import unittest

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

#from mock import Mock

TIMEOUT=300

import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

from softwarecenter.testutils import do_events

class TestGlobalPane(unittest.TestCase):

    def test_spinner_available(self):
        from softwarecenter.ui.gtk3.panes.globalpane import get_test_window
        win = get_test_window()
        pane = win.get_data("pane")
        self.assertNotEqual(pane.spinner, None)
        do_events()


if __name__ == "__main__":
    unittest.main()
