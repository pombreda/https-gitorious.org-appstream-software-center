#!/usr/bin/python

import os
import sys
import unittest
import logging

sys.path.insert(0, '../')


from softwarecenter.enums import PkgStates
from softwarecenter.db.debfile import DebFileApplication
from softwarecenter.testutils import get_test_db

DEBFILE_PATH = './data/test_debs/gdebi-test9.deb'
DEBFILE_NAME = 'gdebi-test9'
DEBFILE_DESCRIPTION = ' provides/conflicts against "nvidia-glx"'

DEBFILE_REINSTALLABLE = './data/test_debs/gdebi-test1.deb'

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

    def test_get_pkg_state_uninstalled(self):
        debfileapplication = DebFileApplication(DEBFILE_PATH)
        debfiledetails = debfileapplication.get_details(self.db)

        self.assertEquals(debfiledetails.pkg_state, PkgStates.UNINSTALLED)

    # disabled until the fixme gets fixed
    def disabled_for_now_test_get_pkg_state_reinstallable(self):
        # FIMXE: add hand crafted dpkg status file into the testdir so
        #        that gdebi-test1 is marked install for the MockAptCache
        debfileapplication = DebFileApplication(DEBFILE_REINSTALLABLE)
        debfiledetails = debfileapplication.get_details(self.db)
        self.assertEquals(debfiledetails.pkg_state, PkgStates.REINSTALLABLE)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
