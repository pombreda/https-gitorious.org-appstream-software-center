#!/usr/bin/python

import os
import unittest

from testutils import setup_test_env
setup_test_env()

from softwarecenter.paths import XAPIAN_BASE_PATH

from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.categories import (
    CategoriesParser, RecommendedForMeCategory,
    get_category_by_name, get_query_for_category)
from softwarecenter.testutils import get_test_db

class TestCategories(unittest.TestCase):
    
    def setUp(self):
        self.db = get_test_db()

    def test_recommends_category(self):
        recommends_cat = RecommendedForMeCategory()
        docids = recommends_cat.get_documents(self.db)
        self.assertEqual(docids, [])
    
    def test_get_query(self):
        query = get_query_for_category(self.db, "Education")
        print query
        self.assertNotEqual(query, None)

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
        self.cats = self.catview.parse_applications_menu(
            '/usr/share/app-install')

    def test_get_cat_by_name(self):
        cat = get_category_by_name(self.cats, 'Games')
        self.assertEqual(cat.untranslated_name, 'Games')
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.untranslated_name, 'Featured')

    def test_cat_has_flags(self):
        cat = get_category_by_name(self.cats, 'Featured')
        self.assertEqual(cat.flags[0], 'carousel-only')

    def test_get_documents(self):
        cat = get_category_by_name(self.cats, 'Featured')
        docs = cat.get_documents(self.db)
        self.assertNotEqual(docs, [])
        for doc in documents:
            self.assertEqual(type(doc), xapian.Document)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
