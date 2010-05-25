#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import unittest

from softwarecenter.view.catview import CategoryView
from softwarecenter.enums import *

class testCatView(unittest.TestCase):

    def setUp(self):
        pass

    def test_add_category(self):
        pass

    def test_application_activated(self):
        pass

    def test_category_selected(self):
        pass
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
