#!/usr/bin/python

import apt
import os
import re
import unittest
import xapian

from piston_mini_client import PistonResponseObject
from mock import Mock, patch

from testutils import setup_test_env
setup_test_env()


from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.enquire import AppEnquire
from softwarecenter.db.database import parse_axi_values_file
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.update import (
    make_doc_from_parser,
    update_from_app_install_data,
    update_from_var_lib_apt_lists,
    update_from_appstream_xml,
    update_from_software_center_agent,
    SCAPurchasedApplicationParser,
    SCAApplicationParser,
    )
from softwarecenter.distro import get_distro
from softwarecenter.enums import (
    XapianValues,
    PkgStates,
    )
from softwarecenter.testutils import (
    get_test_db, 
    get_test_pkg_info,
    make_software_center_agent_subscription_dict,
    make_software_center_agent_app_dict,
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
        db = xapian.WritableDatabase("./data/test.db",
                                     xapian.DB_CREATE_OR_OVERWRITE)
        cache = apt.Cache()
        # monkey patch distro to ensure we get data
        import softwarecenter.distro
        distro = softwarecenter.distro.get_distro()
        distro.get_codename = lambda: "natty"
        # we test against the real https://software-center.ubuntu.com here
        # so we need network
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
                "-icon-" in doc.get_value(XapianValues.ICON))
            # check support url in the DB
            url=doc.get_value(XapianValues.SUPPORT_SITE_URL)
            if url:
                self.assertTrue(url.startswith("http") or
                                url.startswith("mailto:"))

    def test_license_string_data_from_software_center_agent(self):
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        os.environ["SOFTWARE_CENTER_AGENT_HOST"] = "http://sc.staging.ubuntu.com/"
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
        del os.environ["SOFTWARE_CENTER_AGENT_HOST"]

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
        self.assertEqual(appdetails.icon, "expensive-gem-icon-favicon")
        # test PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED
        # test PkgStates.UNKNOWN
        app = Application("Scintillant Orange", "scintillant-orange")
        appdetails = app.get_details(db)
        self.assertEqual(appdetails.pkg_state, PkgStates.NOT_FOUND)
        self.assertEqual(
            appdetails.tags,
            set(['use::converting', 'role::program', 'implemented-in::perl']))

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

    # FIXME: re-enable both tests once sc.staging.ubuntu.com has the new
    #        version of scagent with support for the publication date
    def disabled_test_for_purchase_apps_date_published(self):
        from softwarecenter.testutils import get_test_pkg_info
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        os.environ["SOFTWARE_CENTER_AGENT_HOST"] = "http://sc.staging.ubuntu.com/"
        # staging does not have a valid cert
        os.environ["PISTON_MINI_CLIENT_DISABLE_SSL_VALIDATION"] = "1"
        cache = get_test_pkg_info()
        db = xapian.WritableDatabase("./data/test.db",
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        self.assertTrue(res)

        for p in db.postlist(""):
            doc = db.get_document(p.docid)
            date_published = doc.get_value(XapianValues.DATE_PUBLISHED)
            # make sure that a date_published value is provided
            self.assertNotEqual(date_published, "")
            self.assertNotEqual(date_published, None)
        del os.environ["SOFTWARE_CENTER_AGENT_HOST"]

    def disabled_test_for_purchase_apps_cataloged_time(self):
        from softwarecenter.testutils import get_test_pkg_info
        #os.environ["SOFTWARE_CENTER_DEBUG_HTTP"] = "1"
        os.environ["SOFTWARE_CENTER_AGENT_HOST"] = "http://sc.staging.ubuntu.com/"
        # staging does not have a valid cert
        os.environ["PISTON_MINI_CLIENT_DISABLE_SSL_VALIDATION"] = "1"
        cache = get_test_pkg_info()
        db = xapian.WritableDatabase("./data/test.db",
                                     xapian.DB_CREATE_OR_OVERWRITE)
        res = update_from_software_center_agent(db, cache, ignore_cache=True)
        self.assertTrue(res)
        res = update_from_app_install_data(db, self.cache, datadir="./data/desktop")
        self.assertTrue(res)
        db = StoreDatabase("./data/test.db", self.cache)
        db.open(use_axi=True)

        axi_value_time = db._axi_values["catalogedtime"]
        sc_app = Application("Ubuntu Software Center Test", "software-center")
        sc_doc = db.get_xapian_document(sc_app.appname, sc_app.pkgname)
        sc_cataloged_time = sc_doc.get_value(axi_value_time)
        for_purch_app = Application("For Purchase Test App", "hellox")
        for_purch_doc = db.get_xapian_document(for_purch_app.appname,
                                               for_purch_app.pkgname)
        for_purch_cataloged_time = for_purch_doc.get_value(axi_value_time)
        # the for-purchase test package should be cataloged at a
        # later time than axi package Ubuntu Software Center
        self.assertTrue(for_purch_cataloged_time > sc_cataloged_time)

        del os.environ["SOFTWARE_CENTER_AGENT_HOST"]

    def test_hardware_requirements_satisfied(self):
        with patch.object(AppDetails, 'hardware_requirements') as mock_hw:
            # setup env
            db = get_test_db()
            app = Application("", "software-center")
            mock_hw.__get__ = Mock()
            # not good
            mock_hw.__get__.return_value={
                'hardware::gps' : 'no',
                'hardware::video:opengl' : 'yes',
                }
            details = AppDetails(db, application=app)
            self.assertFalse(details.hardware_requirements_satisfied)
            # this if good
            mock_hw.__get__.return_value={
                'hardware::video:opengl' : 'yes',
                }
            self.assertTrue(details.hardware_requirements_satisfied)
            # empty is satisfied
            mock_hw.__get__.return_value={}
            self.assertTrue(details.hardware_requirements_satisfied)

    @patch("softwarecenter.db.application.RegionDiscover")
    def test_region_requirements_satisfied(self, mock_region_discover):
        mock_region_discover.get_region.return_value = { 
            'country' : 'Germany',
            'countrycode' : 'de',
            }
        with patch.object(AppDetails, 'tags') as mock_tags:
            # setup env
            db = get_test_db()
            app = Application("", "software-center")
            mock_tags.__get__ = Mock()
            # not good
            mock_tags.__get__.return_value = ["region::ZM"]
            details = AppDetails(db, application=app)
            self.assertFalse(details.region_requirements_satisfied)
            # this if good
            mock_tags.__get__.return_value = ["region::DE"]
            self.assertTrue(details.region_requirements_satisfied)
            # empty is satisfied
            mock_region.__get__.return_value=[]
            self.assertTrue(details.region_requirements_satisfied)

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

    def test_appdetails(self):
        from softwarecenter.testutils import get_test_db
        db = get_test_db()
        # see "apt-cache show casper|grep ^Tag"
        details = AppDetails(db, application=Application("", "casper"))
        self.assertTrue(len(details.tags) > 2)

    def test_app_enquire(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open()
        # test the AppEnquire engine
        enquirer = AppEnquire(self.cache, db)
        enquirer.set_query(xapian.Query("a"),
                           nonblocking_load=False)
        self.assertTrue(len(enquirer.get_docids()) > 0)
        # FIXME: test more of the interface


def make_purchased_app_details(db=None, supported_series=None):
    """Return an AppDetail instance with the required attributes."""
    app = make_software_center_agent_app_dict()
    subscription = make_software_center_agent_subscription_dict(app)

    if supported_series != None:
        subscription['application']['series'] = supported_series
    else:
        # If no supportod_series kwarg was provided, we ensure the
        # current series/arch is supported.
        distro = get_distro()
        subscription['application']['series'] = {
            distro.get_codename(): [distro.get_architecture()]
            }

    item = PistonResponseObject.from_dict(subscription)
    parser = SCAPurchasedApplicationParser(item)

    if db is None:
        db = get_test_db()

    doc = make_doc_from_parser(parser, db._aptcache)
    app_details = AppDetails(db, doc)
    return app_details


class AppDetailsSCAApplicationParser(unittest.TestCase):
    
    def setUp(self):
        self.db = get_test_db()

    def _get_app_details_from_app_dict(self, app_dict):
        item = PistonResponseObject.from_dict(app_dict)
        parser = SCAApplicationParser(item)
        doc = make_doc_from_parser(parser, self.db._aptcache)
        app_details = AppDetails(self.db, doc)
        return app_details

    @patch('os.path.exists')
    def test_channel_detection_partner(self, mock):
        # we need to patch os.path.exists as "AppDetails.channelname" will
        # check if there is a matching channel description file on disk
        os.path.exists.return_value = True
        # setup dict
        app_dict = make_software_center_agent_app_dict()
        app_dict["archive_root"] = "http://archive.canonical.com/"
        app_details = self._get_app_details_from_app_dict(app_dict)
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        dist = get_distro().get_codename()
        self.assertEqual(app_details.channelname, "%s-partner" % dist)
    
    @patch('os.path.exists')
    def test_channel_detection_extras(self, mock):
        # we need to patch os.path.exists as "AppDetails.channelname" will
        # check if there is a matching channel description file on disk
        os.path.exists.return_value = True
        # setup dict
        app_dict = make_software_center_agent_app_dict()
        app_dict["archive_root"] = "http://extras.ubuntu.com/"
        app_details = self._get_app_details_from_app_dict(app_dict)
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.channelname, "ubuntu-extras")

    def test_date_no_published(self):
        app_dict = make_software_center_agent_app_dict()
        app_dict["date_published"] = "None"
        app_details = self._get_app_details_from_app_dict(app_dict)
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.date_published, "")
        # and again
        app_dict["date_published"] = "2012-01-21 02:15:10.358926"
        app_details = self._get_app_details_from_app_dict(app_dict)
        # ensure that archive.canonical.com archive roots are detected
        # as the partner channel
        self.assertEqual(app_details.date_published, "2012-01-21 02:15:10")
        

class AppDetailsPkgStateTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set these as class attributes as we don't modify either
        # during the tests.
        cls.distro = get_distro()
        cls.db = get_test_db()

    def test_package_state_purchased_enable_repo(self):
        # If the current series is supported by the app, the state should
        # be PURCHASED_BUT_REPO_MUST_BE_ENABLED.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): [self.distro.get_architecture()]
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)

    def test_package_state_purchased_not_available(self):
        # If the current series is NOT supported by the app, the state should
        # be PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): ['newarch', 'amdm128'],
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_NOT_AVAILABLE_FOR_SERIES,
            state)

    def test_package_state_no_series(self):
        # Until the fix for bug 917109 is deployed on production, we
        # should default to the current (broken) behaviour of
        # indicating that the repo just needs enabling.
        app_details = make_purchased_app_details(self.db, supported_series=None)

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)

    def test_package_state_arch_any(self):
        # In the future the supported arches returned by sca will include
        # any - let's not break when that happens.
        app_details = make_purchased_app_details(self.db,
            supported_series={
                'current-1': ['i386', 'amd64'],
                self.distro.get_codename(): ['newarch', 'any'],
                })

        state = app_details.pkg_state

        self.assertEqual(
            PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED,
            state)



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
