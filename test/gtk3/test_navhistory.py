#!/usr/bin/python

import sys
import unittest

from mock import Mock

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

from softwarecenter.ui.gtk3.session.navhistory import (
    NavigationHistory, NavigationItem)

class MockButton():

    def __init__(self):
        self.sensitive = True

    def set_sensitive(self, val):
        self.sensitive = val

    def has_focus(self):
        return False

class TestNavhistory(unittest.TestCase):
    """ basic tests for navigation history """

    def test_nav_history(self):
        # mock button
        back_forward_btn = Mock()
        back_forward_btn.right = MockButton()
        back_forward_btn.left = MockButton()
        # mock options
        options = Mock()
        options.display_navlog = False
        # create navhistory
        navhistory = NavigationHistory(back_forward_btn, options)

        # mock view manager
        view_manager = Mock()
        view_manager.navhistory = navhistory
        
        # create a NavHistory 
        pane = Mock()
        pane.pane_name = "pane_name"
        # first we must initialize the NavHistory with the equivalent of the initial category view
        item = NavigationItem(view_manager, pane, "cat_page", "cat_state", "cb")
        navhistory.append(item)
        item = NavigationItem(view_manager, pane, "a_page", "a_state", "cb")
        # add a new item and ensure that the button is now sensitive
        navhistory.append(item)
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(back_forward_btn.left.sensitive)
        # navigate back
        navhistory.nav_back()
        self.assertTrue(back_forward_btn.right.sensitive)
        self.assertFalse(back_forward_btn.left.sensitive)
        # navigate forward
        navhistory.nav_forward()
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertTrue(back_forward_btn.left.sensitive)
        # and reset
        navhistory.reset()
        self.assertFalse(back_forward_btn.right.sensitive)
        self.assertFalse(back_forward_btn.left.sensitive)
        self.assertEqual(len(navhistory.stack), 0)
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
