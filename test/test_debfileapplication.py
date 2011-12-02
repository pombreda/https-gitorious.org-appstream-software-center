#!/usr/bin/python

import os
import sys
import unittest
import logging

sys.path.insert(0, '../')


from softwarecenter.enums import PkgStates
from softwarecenter.db.debfile import DebFileApplication
from softwarecenter.testutils import get_test_db

DEBFILE_PATH = '/home/brendand/Downloads/terminator_0.96ppa6_all.deb'
DEBFILE_UNINSTALLED = '/home/brendand/Downloads/shutter_0.88~ppa4~oneiric1_all.deb'

DEBFILE_NAME = 'terminator'
DEBFILE_DESCRIPTION = ' Terminator is a little project to produce an efficient way of\n filling a large area of screen space with terminals.\n The user can have multiple terminals in one window and use\n key bindings to switch between them. See the manpage for\n details.'

class TestDebFileApplication(unittest.TestCase):
    """ Test the class DebFileApplication """

    def setUp(self):
        self.db = get_test_db()

    def test_get_name(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)
        
        self.assertEquals(debfiledetails.name, DEBFILE_NAME)

    def test_get_description(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.description, DEBFILE_DESCRIPTION)

    def test_get_pkg_state_reinstallable(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.pkg_state, PkgStates.REINSTALLABLE)

    def test_get_pkg_state_uninstalled(self):
        debfileapplication = DebFileApplication(DEBFILE_UNINSTALLED)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.pkg_state, PkgStates.UNINSTALLED)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
