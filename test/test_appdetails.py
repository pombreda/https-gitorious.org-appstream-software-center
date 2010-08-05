#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.db.application import Application, AppDetails

class testApplication(unittest.TestCase):

    def setUp(self):
        pass

    def test_application_simple(self):
        app = Application("appname", "pkgname")
        self.assertEqual(app.appname, "appname")
        self.assertEqual(app.pkgname, "pkgname")
        self.assertEqual(app.request, "")
        self.assertEqual(app.popcon, 0)
        # ensure that it fails with no argument (there are not "empty" apps)
        self.assertRaises(ValueError, Application, ())

    def test_application_deb(self):
        app = Application(request="/tmp/2vcard_1.0_all.deb")
        self.assertEqual(app.pkgname, "2vcard")
        self.assertEqual(app.appname, "2vcard")
        app = Application(request="/tmp/apt_2.0_i386.deb")
        self.assertEqual(app.pkgname, "apt")
        self.assertEqual(app.appname, "Apt")
        app = Application(request="/tmp/odd.deb")
        self.assertEqual(app.pkgname, "odd")
        self.assertEqual(app.appname, "Odd")
    

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
