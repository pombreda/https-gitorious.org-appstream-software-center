#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.db.application import Application, DebFileApplication, AppDetails

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
        app = DebFileApplication("/tmp/2vcard_1.0_all.deb")
        self.assertEqual(app.pkgname, "2vcard")
        self.assertEqual(app.appname, "2vcard")
        app = DebFileApplication("/tmp/apt_2.0_i386.deb")
        self.assertEqual(app.pkgname, "apt")
        self.assertEqual(app.appname, "Apt")
        app = DebFileApplication("/tmp/odd.deb")
        self.assertEqual(app.pkgname, "odd")
        self.assertEqual(app.appname, "Odd")
    
    def test_application_with_request(self):
        app = Application("appname", "pkgname?section=universe&section=multiverse")
        self.assertEqual(app.appname, "appname")
        self.assertEqual(app.pkgname, "pkgname")
        self.assertEqual(app.request, "section=universe&section=multiverse")
        app = Application("appname", "pkgname?section=a?section=b")
        self.assertEqual(app.appname, "appname")
        self.assertEqual(app.pkgname, "pkgname")
        self.assertEqual(app.request, "section=a?section=b")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
