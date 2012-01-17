#!/usr/bin/python

import apt_pkg
import apt
import logging
import json
import unittest
import xapian

from piston_mini_client import PistonResponseObject
from testutils import setup_test_env
setup_test_env()

from softwarecenter.enums import XapianValues
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.update import (
    add_from_purchased_but_needs_reinstall_data,
    SCAPurchasedApplicationParser,
    SoftwareCenterAgentParser,
    )

# The original lucid API (1.0) as documented at:
#  https://wiki.canonical.com/Ubuntu/SoftwareCenter/10.10/Roadmap/SoftwareCenterAgent
# is no longer used by USC. The example JSON below should be taken from running
# USC against production.
AVAILABLE_FOR_ME_JSON = """
[
    {
        "deb_line": "deb https://username:randomp3atoken@private-ppa.launchpad.net/mvo/private-test/ubuntu maverick main #Personal access of username to private-test",
        "purchase_price": "19.95",
        "purchase_date": "2010-06-24 20:08:23",
        "state": "Complete",
        "failures": [],
        "open_id": "https://login.ubuntu.com/+id/ABCDEF",
        "application": {
            "archive_id": "mvo/private-test",
            "signing_key_id": "1024R/0EB12F05",
            "name": "Ubiteme",
            "package_name": "hellox",
            "description": "One of the best strategy games you\'ll ever play!"
            },
        "distro_series": {"version": "10.10", "code_name": "maverick"}
    }
]
"""

class MockAvailableForMeItem(object):
    def __init__(self, entry_dict):
        for key, value in entry_dict.iteritems():
            setattr(self, key, value)
        self.MimeType = ""
        self.department = []

class MockAvailableForMeList(list):

    def __init__(self):
        alist = json.loads(AVAILABLE_FOR_ME_JSON)
        for entry_dict in alist:
            self.append(MockAvailableForMeItem(entry_dict))

class TestPurchased(unittest.TestCase):
    """ tests the store database """

    def setUp(self):
        # use fixture apt data
        apt_pkg.config.set("APT::Architecture", "i386")
        apt_pkg.config.set("Dir::State::status",
                           "./data/appdetails/var/lib/dpkg/status")
        # create mocks
        self.available_to_me = MockAvailableForMeList()
        self.cache = apt.Cache()

    def test_reinstall_purchased_mock(self):
        # test if the mocks are ok
        self.assertEqual(len(self.available_to_me), 1)
        self.assertEqual(
            self.available_to_me[0].application['package_name'], "hellox")

    def test_reinstall_purchased_xapian(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open(use_axi=False)
        # now create purchased debs xapian index (in memory because
        # we store the repository passwords in here)
        old_db_len = len(db)
        query = add_from_purchased_but_needs_reinstall_data(
            self.available_to_me, db, self.cache)
        # ensure we have a new item (the available for reinstall one)
        self.assertEqual(len(db), old_db_len+1)
        # query
        enquire = xapian.Enquire(db.xapiandb)
        enquire.set_query(query)
        matches = enquire.get_mset(0, len(db))
        self.assertEqual(len(matches), 1)
        for m in matches:
            doc = db.xapiandb.get_document(m.docid)
            self.assertEqual(doc.get_value(XapianValues.PKGNAME), "hellox")
            self.assertEqual(doc.get_value(XapianValues.ARCHIVE_SIGNING_KEY_ID), "1024R/0EB12F05")
            self.assertEqual(doc.get_value(XapianValues.ARCHIVE_DEB_LINE),
                                           "deb https://username:randomp3atoken@private-ppa.launchpad.net/mvo/private-test/ubuntu maverick main #Personal access of username to private-test")
            break # only one match


class SoftwareCenterAgentParserTestCase(unittest.TestCase):

    # def test_parses_application(self):
    #     self.fail("Unimplemented")
    pass


class SCAPurchasedApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_subscription=None):
        if piston_subscription is None:
            piston_subscription = PistonResponseObject.from_dict(
                json.loads(AVAILABLE_FOR_ME_JSON)[0])

        return SCAPurchasedApplicationParser(piston_subscription)

    def test_get_desktop_subscription(self):
        parser = self._make_application_parser()

        expected_results = {
            "Deb-Line": "deb https://username:randomp3atoken@"
                        "private-ppa.launchpad.net/mvo/private-test/ubuntu "
                        "maverick main #Personal access of username to "
                        "private-test",
            "Purchased-Date": "2010-06-24 20:08:23",
            }
        for key in expected_results:
            result = parser.get_desktop(key)
            self.assertEqual(expected_results[key], result)

    def test_get_desktop_application(self):
        # The parser passes application attributes through to
        # an application parser for handling.
        parser = self._make_application_parser()

        expected_results = {
            "Name": "Ubiteme (already purchased)",
            "Package": "hellox",
            "Signing-Key-Id": "1024R/0EB12F05",
            "PPA": "mvo/private-test",
            }
        for key in expected_results.keys():
            result = parser.get_desktop(key)
            self.assertEqual(expected_results[key], result)

    def test_has_option_desktop_includes_app_keys(self):
        # The SCAPurchasedApplicationParser handles application keys also
        # (passing them through to the composited application parser).
        parser = self._make_application_parser()

        for key in ('Name', 'Package', 'Signing-Key-Id', 'PPA'):
            self.assertTrue(parser.has_option_desktop(key))
        for key in ('Deb-Line', 'Purchased-Date'):
            self.assertTrue(parser.has_option_desktop(key),
                    'Key: {0} was not an option.'.format(key))

    def test_license_key_present(self):
        piston_subscription = PistonResponseObject.from_dict(
            json.loads(AVAILABLE_FOR_ME_JSON)[0])
        piston_subscription.license_key = 'abcd'
        piston_subscription.license_key_path = '/foo'
        parser = self._make_application_parser(piston_subscription)

        self.assertTrue(parser.has_option_desktop('License-Key'))
        self.assertTrue(parser.has_option_desktop('License-Key-Path'))
        self.assertEqual('abcd', parser.get_desktop('License-Key'))
        self.assertEqual('/foo', parser.get_desktop('License-Key-Path'))

    def test_license_key_not_present(self):
        parser = self._make_application_parser()

        self.assertFalse(parser.has_option_desktop('License-Key'))
        self.assertFalse(parser.has_option_desktop('License-Key-Path'))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
