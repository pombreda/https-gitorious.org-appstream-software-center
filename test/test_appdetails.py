#!/usr/bin/python

import os
import sys
sys.path.insert(0,"../")

import apt
import unittest
import shutil

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.application import Application, DebFileApplication, AppDetails, AppDetailsDebFile
from softwarecenter.enums import XAPIAN_BASE_PATH, PKG_STATE_UNKNOWN, PKG_STATE_UNINSTALLED
from softwarecenter.db.database import StoreDatabase

class testApplication(unittest.TestCase):

    def setUp(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.cache = AptCache()
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open()

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

    def test_appdetails_simple(self):
        # display name is the summary for packages (per spec)
        app = Application("", "apt")
        appdetails = AppDetails(self.db, application=app)
        self.assertEqual(appdetails.display_name,
                         "Advanced front-end for dpkg")
        # appname
        app = Application("7zip", "p7zip-full")
        appdetails = app.get_details(self.db)
        self.assertEqual(appdetails.display_name,
                         "7zip")

    def test_appdetails_from_deb(self):
        app = DebFileApplication("./data/test_debs/gdebi-test1.deb")
        appdetails = AppDetailsDebFile(self.db, application=app)
        self.assertEqual(appdetails._pkg, None)
        self.assertTrue(appdetails.error.startswith("Conflicts with "))
        # state unknown because of the error
        self.assertEqual(appdetails.pkg_state, PKG_STATE_UNKNOWN)

        # test details getting
        app = DebFileApplication("./data/test_debs/gdebi-test3.deb")
        appdetails = app.get_details(self.db)
        self.assertEqual(appdetails._pkg, None)
        self.assertEqual(appdetails.error, None)
        s = "testpackage for gdebi - or-group (impossible-dependency|apt)"
        self.assertEqual(appdetails.summary, s)
        self.assertEqual(appdetails.display_summary, s)
        # state unknown because of the error
        self.assertEqual(appdetails.pkg_state, PKG_STATE_UNINSTALLED)
        self.assertEqual(appdetails.warning,
                         "Only install this file if you trust the origin.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
