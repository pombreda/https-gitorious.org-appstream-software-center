#!/usr/bin/python

import os
import unittest


from testutils import setup_test_env
setup_test_env()
from softwarecenter.region import RegionDiscover
from softwarecenter.i18n import init_locale

class TestRegion(unittest.TestCase):
    """ tests the region detection """

    def setUp(self):
        self.region = RegionDiscover()

    def test_get_region_dump(self):
        os.environ["LANG"] = "en_ZM.utf8"
        init_locale()
        res = self.region._get_region_dumb()
        self.assertEqual(res["countrycode"], "ZM")
        self.assertEqual(res["country"], "Zambia")
        os.environ["LANG"] = ""

    def test_get_region_geoclue(self):
        res = self.region._get_region_geoclue()
        self.assertNotEqual(len(res), 0)
        self.assertTrue("countrycode" in res)
        self.assertTrue("country" in res)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
