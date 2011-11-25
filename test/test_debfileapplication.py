#!/usr/bin/python

import os
import sys
import unittest

sys.path.insert(0, '../')

from softwarecenter.db.debfile import DebFileApplication

DEBFILE_PATH = '/home/brendand/checkbox_0.13.1+bzr1129+201111241945~oneiric1_i386.deb'

class TestDebFileApplication(unittest.TestCase):
    """ Test the class DebFileApplication """

    def setup(self):
        self.debfileapplication = DebFileApplication(DEBFILE_PATH)
