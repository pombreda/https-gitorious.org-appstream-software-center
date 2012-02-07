#!/usr/bin/python

import os
import unittest
import xapian
from mock import patch

from testutils import setup_test_env
setup_test_env()

from softwarecenter.paths import XAPIAN_BASE_PATH

from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.db.categories import (
    CategoriesParser, RecommendedForYouCategory,
    get_category_by_name, get_query_for_category)
from softwarecenter.testutils import (get_test_db,
                                      make_recommender_agent_recommend_top_dict)

class TestCategories(unittest.TestCase):
    
    def setUp(self):
        self.db = get_test_db()

    @patch('softwarecenter.db.categories.RecommenderAgent')
    def test_recommends_category(self, AgentMockCls):
        # ensure we use the same instance in test and code
        agent_mock_instance = AgentMockCls.return_value
        recommends_cat = RecommendedForYouCategory()
        docids = recommends_cat.get_documents(self.db)
        self.assertEqual(docids, [])
        self.assertTrue(agent_mock_instance.query_recommend_top.called)
        # ensure we get a query when the callback is called
        recommends_cat._recommend_top_result(
                                None, 
                                make_recommender_agent_recommend_top_dict())
        self.assertNotEqual(recommends_cat.get_documents(self.db), [])
   
    def test_get_query(self):
        query = get_query_for_category(self.db, "Education")
        self.assertNotEqual(query, None)

class TestCatParsing(unittest.TestCase):
    """ tests the "where is it in the menu" code """

    def setUp(self):
        self.db = get_test_db()
        parser = CategoriesParser(self.db)
        self.cats = parser.parse_applications_menu(
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
        for doc in docs:
            self.assertEqual(type(doc), xapian.Document)



if __name__ == "__main__":
    import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
