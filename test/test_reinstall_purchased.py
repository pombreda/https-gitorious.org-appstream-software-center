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

# Example taken from running:
# PYTHONPATH=. utils/piston-helpers/piston_generic_helper.py --output=pickle \
#           --debug --needs-auth SoftwareCenterAgentAPI subscriptions_for_me
# then:
#    f = open('my_subscriptions.pickle')
#    subscriptions = pickle.load(f)
#    completed_subs = [subs for subs in subscriptions if subs.state=='Complete']
#    completed_subs[0].__dict__
SUBSCRIPTIONS_FOR_ME_JSON = """
[
    {
         "deb_line": "deb https://username:random3atoken@private-ppa.launchpad.net/commercial-ppa-uploaders/photobomb/ubuntu natty main",
         "purchase_price": "2.99",
         "purchase_date": "2011-09-16 06:37:52",
         "state": "Complete",
         "failures": [],
         "open_id": "https://login.ubuntu.com/+id/ABCDEF",
         "application": {
              "archive_id": "commercial-ppa-uploaders/photobomb",
              "signing_key_id": "1024R/75254D99",
              "name": "Photobomb",
              "package_name": "photobomb",
              "description": "Easy and Social Image Editor\\nPhotobomb give you easy access to images in your social networking feeds, pictures on your computer and peripherals, and pictures on the web, and let\'s you draw, write, crop, combine, and generally have a blast mashing \'em all up. Then you can save off your photobomb, or tweet your creation right back to your social network."
         },
         "distro_series": {"code_name": "natty", "version": "11.04"}
    }
]
"""
# Taken directly from:
# https://software-center.ubuntu.com/api/2.0/applications/en/ubuntu/oneiric/i386/
AVAILABLE_APPS_JSON = """
[
    {
        "archive_id": "commercial-ppa-uploaders/fluendo-dvd",
        "signing_key_id": "1024R/75254D99",
        "license": "Proprietary",
        "name": "Fluendo DVD Player",
        "package_name": "fluendo-dvd",
        "support_url": "",
        "series": {
            "maverick": [
                "i386",
                "amd64"
            ],
            "natty": [
                "i386",
                "amd64"
            ],
            "oneiric": [
                "i386",
                "amd64"
            ]
        },
        "price": "24.95",
        "demo": null,
        "date_published": "2011-12-05 18:43:21.653868",
        "status": "Published",
        "channel": "For Purchase",
        "icon_data": "...",
        "department": [
            "Sound & Video"
        ],
        "archive_root": "https://private-ppa.launchpad.net/",
        "screenshot_url": "http://software-center.ubuntu.com/site_media/screenshots/2011/05/fluendo-dvd-maverick_.png",
        "tos_url": "https://software-center.ubuntu.com/licenses/3/",
        "icon_url": "http://software-center.ubuntu.com/site_media/icons/2011/05/fluendo-dvd.png",
        "categories": "AudioVideo",
        "description": "Play DVD-Videos\r\n\r\nFluendo DVD Player is a software application specially designed to\r\nreproduce DVD on Linux/Unix platforms, which provides end users with\r\nhigh quality standards.\r\n\r\nThe following features are provided:\r\n* Full DVD Playback\r\n* DVD Menu support\r\n* Fullscreen support\r\n* Dolby Digital pass-through\r\n* Dolby Digital 5.1 output and stereo downmixing support\r\n* Resume from last position support\r\n* Subtitle support\r\n* Audio selection support\r\n* Multiple Angles support\r\n* Support for encrypted discs\r\n* Multiregion, works in all regions\r\n* Multiple video deinterlacing algorithms"
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
        alist = json.loads(SUBSCRIPTIONS_FOR_ME_JSON)
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
            self.available_to_me[0].application['package_name'], "photobomb")

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
            self.assertEqual(doc.get_value(XapianValues.PKGNAME), "photobomb")
            self.assertEqual(
                doc.get_value(XapianValues.ARCHIVE_SIGNING_KEY_ID),
                "1024R/75254D99")
            self.assertEqual(doc.get_value(XapianValues.ARCHIVE_DEB_LINE),
                "deb https://username:random3atoken@"
                 "private-ppa.launchpad.net/commercial-ppa-uploaders"
                 "/photobomb/ubuntu natty main")


class SoftwareCenterAgentParserTestCase(unittest.TestCase):

    def test_parses_application_from_available_apps(self):
        pass


class SCAPurchasedApplicationParserTestCase(unittest.TestCase):

    def _make_application_parser(self, piston_subscription=None):
        if piston_subscription is None:
            piston_subscription = PistonResponseObject.from_dict(
                json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])

        return SCAPurchasedApplicationParser(piston_subscription)

    def test_get_desktop_subscription(self):
        parser = self._make_application_parser()

        expected_results = {
             "Deb-Line": "deb https://username:random3atoken@"
                         "private-ppa.launchpad.net/commercial-ppa-uploaders"
                         "/photobomb/ubuntu natty main",
             "Purchased-Date": "2011-09-16 06:37:52",
            }
        for key in expected_results:
            result = parser.get_desktop(key)
            self.assertEqual(expected_results[key], result)

    def test_get_desktop_application(self):
        # The parser passes application attributes through to
        # an application parser for handling.
        parser = self._make_application_parser()

        expected_results = {
            "Name": "Photobomb (already purchased)",
            "Package": "photobomb",
            "Signing-Key-Id": "1024R/75254D99",
            "PPA": "commercial-ppa-uploaders/photobomb",
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
            json.loads(SUBSCRIPTIONS_FOR_ME_JSON)[0])
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
