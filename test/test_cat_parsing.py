#!/usr/bin/python

import os
import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.paths import XAPIAN_BASE_PATH

from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.categories import CategoriesParser, get_category_by_name


class TestCatParsing(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        cache = get_pkg_info()
        cache.open()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.db = StoreDatabase(pathname, cache)
        self.db.open()
        self.catview = CategoriesParser(self.db)
        self.catview.db = self.db
        self.cats = self.catview.parse_applications_menu('/usr/share/app-install')

    def test_get_cat_by_name(self):
        cat = get_category_by_name(self.cats, 'Games')
        self.assertEqual(cat.untranslated_name, 'Games')
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.untranslated_name, 'Featured')

    def test_cat_has_flags(self):
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.flags[0], 'carousel-only')


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
