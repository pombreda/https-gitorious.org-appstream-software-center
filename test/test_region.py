#!/usr/bin/python

import os
import unittest


from testutils import setup_test_env
setup_test_env()
from softwarecenter.region import get_region, get_region_geoclue
from softwarecenter.i18n import init_locale

class TestRegion(unittest.TestCase):
    """ tests the region detection """

    def tearDown(self):
        os.environ["LANG"] = ""
        
    def test_get_region(self):
        os.environ["LANG"] = "en_ZM.utf8"
        init_locale()
        self.assertEqual(get_region(), "ZM")

    def test_get_region_geoclue(self):
        res = get_region_geoclue()
        self.assertNotEqual(len(res), 0)
        self.assertTrue("countrycode" in res)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
