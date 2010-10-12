#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt_pkg
import apt
import os
import re
import unittest
import xapian

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.db.update import update_from_app_install_data, update_from_var_lib_apt_lists
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.enums import *

class TestMime(unittest.TestCase):
    """ tests the mime releated stuff """

    def setUp(self):
        self.cache = AptCache()

    def test_most_popular_applications_for_mimetype(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        # all
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=False, num=5)
        self.assertEqual(len(result), 5)
        # only_uninstaleld
        result = db.get_most_popular_applications_for_mimetype("text/html", only_uninstalled=True, num=2)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
