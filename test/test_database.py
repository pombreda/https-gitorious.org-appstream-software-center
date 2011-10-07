#!/usr/bin/python


import sys
sys.path.insert(0,"../")

import apt
import os
import re
import unittest
import xapian

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.update import update_from_app_install_data, update_from_var_lib_apt_lists, update_from_appstream_xml
from softwarecenter.enums import (
    XapianValues,
    PkgStates,
    )

class TestDatabase(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        apt.apt_pkg.config.set("Dir::State::status",
                               "./data/appdetails/var/lib/dpkg/status")
        self.cache = get_pkg_info()
        self.cache.open()

    def test_update_from_desktop_file(self):
        # ensure we index with german locales to test i18n
        os.environ["LANGUAGE"] = "de"
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/desktop")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 5)
        # test if Name[de] was picked up
        i=0
        for it in db.postlist("AAUbuntu Software Zentrum"):
            i+=1
        self.assertEqual(i, 1)

    def test_update_from_appstream_xml(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_appstream_xml(db, self.cache, "./data/app-info/")
        self.assertTrue(res)
        self.assertEqual(db.get_doccount(), 1)
        # FIXME: improve tests
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            for term in doc.termlist():
                print term, term.term
            for value in doc.values():
                print value, value.num, value.value

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
        # monkey patch distro to ensure we get data
        import softwarecenter.distro
        distro = softwarecenter.distro.get_distro()
        distro.get_codename = lambda: "natty"
        # we test against the real https://software-center.ubuntu.com here
        # so we need network
        softwarecenter.paths.datadir="../data"
        os.environ["PYTHONPATH"] = ".."
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        # check results
        self.assertTrue(res)
        self.assertTrue(db.get_doccount() > 1)
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            ppa = doc.get_value(XapianValues.ARCHIVE_PPA)
            self.assertTrue(ppa.startswith("commercial-ppa") and
                            ppa.count("/") == 1, 
                            "ARCHIVE_PPA value incorrect, got '%s'" % ppa)
            self.assertTrue(
                doc.get_value(XapianValues.ICON).startswith("sc-agent"))

    def test_license_string_data_from_software_center_agent(self):
        from softwarecenter.db.update import update_from_software_center_agent
        from softwarecenter.testutils import get_test_pkg_info
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        os.environ["SOFTWARE_CENTER_BUY_HOST"] = "http://sc.staging.ubuntu.com/"
        # staging does not have a valid cert
        os.environ["PISTON_MINI_CLIENT_DISABLE_SSL_VALIDATION"] = "1"
        cache = get_test_pkg_info()
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        self.assertTrue(res)
        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            license = doc.get_value(XapianValues.LICENSE)
            self.assertNotEqual(license, "")
            self.assertNotEqual(license, None)
        del os.environ["SOFTWARE_CENTER_BUY_HOST"]

    def test_application(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        # fail if AppDetails(db) without document= or application=
        # is run
        self.assertRaises(ValueError, AppDetails, db)

    def test_application_details(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/desktop")
        self.assertTrue(res)
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=False, use_agent=False)
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
        # test get_appname and get_pkgname
        self.assertEqual(db.get_appname(doc), "Ubuntu Software Center Test")
        self.assertEqual(db.get_pkgname(doc), "software-center")
        # test appdetails
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
        self.assertEqual(appdetails.pkg_state, PkgStates.INSTALLED)
        # FIXME: test description for unavailable pkg
        self.assertTrue(
            appdetails.description.startswith("Ubuntu Software Center lets you"))
        # FIXME: test appdetails.website
        self.assertEqual(appdetails.icon, "softwarecenter")
        # crude, crude
        self.assertTrue(len(appdetails.version) > 2)
        # FIXME: screenshots will only work on ubuntu
        self.assertTrue(re.match(
                "http://screenshots.ubuntu.com/screenshot-with-version/software-center/[\d.]+", 
                appdetails.screenshot))
        self.assertTrue(re.match(
                "http://screenshots.ubuntu.com/thumbnail-with-version/software-center/[\d.]+",
                appdetails.thumbnail))
        # FIXME: add document that has a price
        self.assertEqual(appdetails.price, '')
        self.assertEqual(appdetails.license, "Open source")
        # test lazy history loading for installation date
        self.ensure_installation_date_and_lazy_history_loading(appdetails)
        # test apturl replacements
        # $kernel
        app = Application("", "linux-headers-$kernel", "channel=$distro-partner")
        self.assertEqual(app.pkgname, 'linux-headers-'+os.uname()[2])
        # $distro
        details = app.get_details(db)
        from softwarecenter.distro import get_distro
        distro = get_distro().get_codename()
        self.assertEqual(app.request, 'channel=' + distro + '-partner')
        
    def ensure_installation_date_and_lazy_history_loading(self, appdetails):
        # we run two tests, the first is to ensure that we get a 
        # result from installation_data immediately (at this point the
        # history is not loaded yet) so we expect "None"
        self.assertEqual(appdetails.installation_date, None)
        # then we need to wait until the history is loaded in the idle
        # handler
        from gi.repository import GObject
        context = GObject.main_context_default()
        while context.pending():
            context.iteration()
        # ... and finally we test that its really there
        # FIXME: this will only work if software-center is installed
        self.assertNotEqual(appdetails.installation_date, None)

    def test_package_states(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/desktop")
        self.assertTrue(res)
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=False)
        # test PkgStates.INSTALLED
        # FIXME: this will only work if software-center is installed
        app = Application("Ubuntu Software Center Test", "software-center")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.INSTALLED)
        # test PkgStates.UNINSTALLED
        # test PkgStates.UPGRADABLE
        # test PkgStates.REINSTALLABLE
        # test PkgStates.INSTALLING
        # test PkgStates.REMOVING
        # test PkgStates.UPGRADING
        # test PkgStates.NEEDS_SOURCE
        app = Application("Zynjacku Test", "zynjacku-fake")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NEEDS_SOURCE)
        # test PkgStates.NEEDS_PURCHASE
        app = Application("The expensive gem", "expensive-gem")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NEEDS_PURCHASE)
        self.assertEqual(appdetails.icon_url, "http://www.google.com/favicon.ico")
        self.assertEqual(appdetails.icon, "favicon")
        # test PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED
        # test PkgStates.UNKNOWN
        app = Application("Scintillant Orange", "scintillant-orange")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NOT_FOUND)

    def test_packagename_is_application(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        # apt has no app
        self.assertEqual(db.get_apps_for_pkgname("apt"), set())
        # but software-center has
        self.assertEqual(len(db.get_apps_for_pkgname("software-center")), 1)

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
            doc = m.document
            doc.get_value(value_time) >= last_time
            last_time = doc.get_value(value_time)
            
    def test_non_axi_apps_cataloged_time(self):
        db = xapian.WritableDatabase("./data/test.db", 
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_app_install_data(db, self.cache, datadir="./data/desktop")
        self.assertTrue(res)
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=True)

        axi_value_time = db._axi_values["catalogedtime"]
        sc_app = Application("Ubuntu Software Center Test", "software-center")
        sc_doc = db.get_xapian_document(sc_app.appname, sc_app.pkgname)
        sc_cataloged_time = sc_doc.get_value(axi_value_time)
        so_app = Application("Scintillant Orange", "scintillant-orange")
        so_doc = db.get_xapian_document(so_app.appname, so_app.pkgname)
        so_cataloged_time = so_doc.get_value(axi_value_time)
        # the test package Scintillant Orange should be cataloged at a
        # later time than axi package Ubuntu Software Center
        self.assertTrue(so_cataloged_time > sc_cataloged_time)

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
        #db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        axi_values = parse_axi_values_file("axi-test-values")
        self.assertNotEqual(axi_values, {})
        print axi_values

    def test_app_enquire(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        # test the AppEnquire engine
        enquirer = AppEnquire(self.cache, db)
        enquirer.set_query(xapian.Query("a"),
                           nonblocking_load=False)
        self.assertTrue(len(enquirer.get_docids()) > 0)
        # FIXME: test more of the interface

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
