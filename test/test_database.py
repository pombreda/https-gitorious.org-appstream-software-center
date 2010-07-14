#!/usr/bin/python


import sys
sys.path.insert(0,"../")

import apt_pkg
import apt
import os
import unittest
import xapian

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.update import update_from_app_install_data, update_from_var_lib_apt_lists
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.enums import *

class testDatabase(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        apt_pkg.config.set("APT::Architecture", "i386")
        apt_pkg.config.set("Dir::State::status",
                           "./data/appdetails/var/lib/dpkg/status")
        self.cache = AptCache()

    def test_comma_seperation(self):
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        db = StoreDatabase(pathname, self.cache)
        # normal
        querries = db._comma_expansion("apt,2vcard,7zip")
        self.assertEqual(len(querries), 3)
        # multiple identical
        querries = db._comma_expansion("apt,apt,apt")
        self.assertEqual(len(querries), 1)
        # too many commas
        querries = db._comma_expansion(",,,apt,xxx,,,")
        self.assertEqual(len(querries), 2)
        # invalid query
        querries = db._comma_expansion("??")
        self.assertEqual(querries, None)

    def test_update_from_desktop_file(self):
        # ensure we index with german locales to test i18n
        os.environ["LANGUAGE"] = "de"
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 5)
        # test if Name[de] was picked up
        i=0
        for it in db.postlist("AAUbuntu Software Zentrum"):
            i+=1
        self.assertEqual(i, 1)

    def test_update_from_var_lib_apt_lists(self):
        # ensure we index with german locales to test i18n
        os.environ["LANGUAGE"] = "de"
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_var_lib_apt_lists(db, self.cache, listsdir="./data/app-info/")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)
        # test if Name-de was picked up
        i=0
        for it in db.postlist("AAFestplatten Ueberpruefer"):
            i+=1
        self.assertEqual(i, 1)
        # test if gettext worked
        found_gettext_translation = False
        for it in db.postlist("AAFestplatten Ueberpruefer"):
            doc = db.get_document(it.docid)
            for term_iter in doc.termlist():
                # a german term from the app-info file to ensure that
                # it got indexed in german
                if term_iter.term == "platzes":
                    found_gettext_translation = True
                    break
        self.assertTrue(found_gettext_translation)

    def test_update_from_json_string(self):
        from softwarecenter.db.update import update_from_json_string
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        cache = apt.Cache()
        p = os.path.abspath("./data/app-info-json/apps.json")
        res = update_from_json_string(db, cache, open(p).read(), origin=p)
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)

    def test_build_from_software_center_agent(self):
        from softwarecenter.db.update import update_from_software_center_agent
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        cache = apt.Cache()
        # do not fail if no software-center agent is running
        try:
            res = update_from_software_center_agent(db, cache)
            self.assertTrue(res)
            self.assertEqual(db.get_doccount(), 1)
        except AttributeError:
            pass
        
    def test_application(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        # fail if AppDetails(db) without document= or application=
        # is run
        self.assertRaises(ValueError, AppDetails, db)

    def test_application_details(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/")
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=False)
        self.assertEqual(len(db), 5)
        # test details
        app = Application("Ubuntu Software Center Test", "software-center")
        details = app.get_details(db)
        self.assertNotEqual(details, None)
        self.assertEqual(details.component, "main")
        self.assertEqual(details.pkgname, "software-center")
        # get the first document
        for doc in db:
            if doc.get_data() == "Ubuntu Software Center Test":
                appdetails = AppDetails(db, doc=doc)
                break
        self.assertEqual(appdetails.name, "Ubuntu Software Center Test")
        self.assertEqual(appdetails.pkgname, "software-center")
        # FIXME: add a dekstop file with a real channel to test
        #        and monkey-patch/modify the APP_INSTALL_CHANNELS_PATH
        self.assertEqual(appdetails.channelname, None)
        self.assertEqual(appdetails.channelfile, None)
        self.assertEqual(appdetails.component, "main")
        self.assertNotEqual(appdetails.pkg, None)
        # from the fake test/data/appdetails/var/lib/dpkg/status
        self.assertEqual(appdetails.pkg.is_installed, True)
        self.assertEqual(appdetails.pkg_state, PKG_STATE_INSTALLED)
        # FIXME: test description for unavailable pkg
        self.assertTrue(
            appdetails.description.startswith("The Ubuntu Software Center"))
        # FIXME: test appdetails.website
        self.assertEqual(appdetails.icon, "softwarecenter")
        # crude, crude
        self.assertTrue(len(appdetails.version) > 2)
        # FIXME: screenshots will only work on ubuntu
        self.assertEqual(appdetails.screenshot,
                         "http://screenshots.ubuntu.com/screenshot-404/software-center")
        self.assertEqual(appdetails.thumbnail,
                         "http://screenshots.ubuntu.com/thumbnail-404/software-center")
        # FIXME: add document that has a price
        self.assertEqual(appdetails.price, '')
        self.assertEqual(appdetails.license, "Open Source")
        # FIXME: this will only work if software-center is installed
        self.assertNotEqual(appdetails.installation_date, None)
        
    def test_package_states(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/")
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=False)
        # test PKG_STATE_INSTALLED
        # FIXME: this will only work if software-center is installed
        app = Application("Ubuntu Software Center Test", "software-center")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PKG_STATE_INSTALLED)
        # test PKG_STATE_UNINSTALLED
        # test PKG_STATE_UPGRADABLE
        # test PKG_STATE_REINSTALLABLE
        # test PKG_STATE_INSTALLING
        # test PKG_STATE_REMOVING
        # test PKG_STATE_UPGRADING
        # test PKG_STATE_NEEDS_SOURCE
        app = Application("Zynjacku Test", "zynjacku-fake")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PKG_STATE_NEEDS_SOURCE)
        # test PKG_STATE_NEEDS_PURCHASE
        app = Application("The expensive gem", "expensive-gem")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PKG_STATE_NEEDS_PURCHASE)
        # test PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED
        # test PKG_STATE_UNKNOWN
        app = Application("Scintillant Orange", "scintillant-orange")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PKG_STATE_UNKNOWN)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
