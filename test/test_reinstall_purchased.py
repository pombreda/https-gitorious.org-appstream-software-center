#!/usr/bin/python


import sys
sys.path.insert(0,"../")

import apt_pkg
import apt
import logging
import os
import simplejson
import unittest
import xapian

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.enums import *
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.update import add_from_puchased_but_needs_reinstall_data

# from
#  https://wiki.canonical.com/Ubuntu/SoftwareCenter/10.10/Roadmap/SoftwareCenterAgent
AVAILABLE_FOR_ME_JSON = """
[
    {
        "archive_id": "mvo/private-test",
        "deb_line": "deb https://username:randomp3atoken@private-ppa.launchpad.net/mvo/private-test/ubuntu maverick main #Personal access of username to private-test",
        "purchase_price": "19.95",
        "purchase_date": "2010-06-24 20:08:23",
        "name": "Ubiteme",
        "description": "One of the best strategy games you\'ll ever play!",
        "package_name": "hellox",
        "signing_key_id": "1024R/0EB12F05",
        "series": {"maverick": ["i386"], "lucid": ["i386", "amd64"]}
    }
]
"""

class MockAvailableForMeItem(object):
    def __init__(self, entry_dict):
        for key, value in entry_dict.iteritems():
            setattr(self, key, value)
            
class MockAvailableForMeList(list):

    def __init__(self):
        alist = simplejson.loads(AVAILABLE_FOR_ME_JSON)
        for entry_dict in alist:
            self.append(MockAvailableForMeItem(entry_dict))

class testPurchased(unittest.TestCase):
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
        self.assertEqual(self.available_to_me[0].package_name, "hellox")

    def test_reinstall_purchased_xapian(self):
        db = StoreDatabase("/var/cache/software-center/xapian", self.cache)
        db.open(use_axi=False)
        # now create purchased debs xapian index (in memory because
        # we store the repository passwords in here)
        old_db_len = len(db)
        query = add_from_puchased_but_needs_reinstall_data(self.available_to_me,
                                                           db, self.cache)
        # ensure we have a new item (the available for reinstall one)
        self.assertEqual(len(db), old_db_len+1)
        # query
        enquire = xapian.Enquire(db.xapiandb)
        enquire.set_query(query)
        matches = enquire.get_mset(0, len(db))
        self.assertEqual(len(matches), 1)
        for m in matches:
            doc = db.xapiandb.get_document(m.docid)
            self.assertEqual(doc.get_value(XAPIAN_VALUE_PKGNAME), "hellox")
            self.assertEqual(doc.get_value(XAPIAN_VALUE_ARCHIVE_SIGNING_KEY_ID), "1024R/0EB12F05")
            self.assertEqual(doc.get_value(XAPIAN_VALUE_ARCHIVE_DEB_LINE),
                                           "deb https://username:randomp3atoken@private-ppa.launchpad.net/mvo/private-test/ubuntu maverick main #Personal access of username to private-test")
            break # only one match
        
if __name__ == "__main__":
    unittest.main()
