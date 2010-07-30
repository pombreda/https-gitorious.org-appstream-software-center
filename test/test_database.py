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
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.db.update import update_from_app_install_data, update_from_var_lib_apt_lists
from softwarecenter.enums import *

class testDatabase(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        apt_pkg.config.set("APT::Architecture", "i386")
        apt_pkg.config.set("Dir::State::status",
                           "./data/appdetails/var/lib/dpkg/status")
        self.cache = apt.Cache()

    def test_comma_seperation(self):
        db = StoreDatabase("/var/cache/software-center/xapian", 
                           self.cache)
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
        self.assertEqual(db.get_doccount(), 1)
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
        self.assertTrue(len(db), 1)
        # test details
        app = Application("Ubuntu Software Center Test", "software-center")
        details = app.get_details(db)
        self.assertNotEqual(details, None)
        self.assertEqual(details.component, "main")
        # get the first document
        for doc in db:
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
        self.assertEqual(appdetails.price, "Free")
        self.assertEqual(appdetails.license, "Open Source")
        # FIXME: this will only work if software-center is installed
        self.assertNotEqual(appdetails.installation_date, None)

    def test_whats_new(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        query = xapian.Query("")
        enquire = xapian.Enquire(db.xapiandb)
        enquire.set_query(query)
        value_time = db._axi_values["catalogedtime"]
        enquire.set_sort_by_value(value_time, reverse=True)
        matches = enquire.get_mset(0, 20)
        last_time = 0
        for m in matches:
            doc = m[xapian.MSET_DOCUMENT]
            doc.get_value(value_time) >= last_time
            last_time = doc.get_value(value_time)

    def test_parse_axi_values_file(self):
        s = """
# This file contains the mapping between names of numeric values indexed in the
# APT Xapian index and their index
#
# Xapian allows to index numeric values as well as keywords and to use them for
# all sorts of useful querying tricks.  However, every numeric value needs to
# have a unique index, and this configuration file is needed to record which
# indices are allocated and to provide a mnemonic name for them.
#
# The format is exactly like /etc/services with name, number and optional
# aliases, with the difference that the second column does not use the
# "/protocol" part, which would be meaningless here.

version	0	# package version
catalogedtime	1	# Cataloged timestamp
installedsize	2	# installed size
packagesize	3	# package size
app-popcon	4	# app-install .desktop popcon rank
"""
        open("axi-test-values","w").write(s)
        db = StoreDatabase("/var/cache/software-center/xapian", 
                           self.cache)
        axi_values = parse_axi_values_file("axi-test-values")
        self.assertNotEqual(axi_values, {})
        print axi_values

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
