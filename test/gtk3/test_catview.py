import time
import unittest

from gi.repository import Gtk
from mock import patch, Mock

from testutils import setup_test_env
setup_test_env()

import softwarecenter.distro
import softwarecenter.paths

from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import SortMethods
from softwarecenter.testutils import (
    FakedCache,
    get_test_db,
    make_recommender_agent_recommend_me_dict,
    ObjectWithSignals,
)
from softwarecenter.ui.gtk3.views import catview_gtk
from softwarecenter.ui.gtk3.views.catview_gtk import get_test_window_catview
from softwarecenter.ui.gtk3.widgets.containers import FramedHeaderBox
from softwarecenter.ui.gtk3.widgets.spinner import SpinnerNotebook


class TestCatView(unittest.TestCase):

    def setUp(self):
        self._cat = None
        self.db = get_test_db()

    def _on_category_selected(self, subcatview, category):
        self._cat = category

    def test_top_rated(self):
        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        lobby = win.get_data("lobby")

        # simulate review-stats refresh
        lobby._update_top_rated_content = Mock()
        lobby.reviews_loader.emit("refresh-review-stats-finished", [])
        self.assertTrue(lobby._update_top_rated_content.called)

        # test clicking top_rated
        lobby.connect("category-selected", self._on_category_selected)
        lobby.top_rated_frame.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Top Rated")
        self.assertEqual(self._cat.sortmode, SortMethods.BY_TOP_RATED)

    def test_new(self):
        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        lobby = win.get_data("lobby")

        # test db reopen triggers whats-new update
        lobby._update_whats_new_content = Mock()
        lobby.db.emit("reopen")
        self.assertTrue(lobby._update_whats_new_content.called)

        # test clicking new
        lobby.connect("category-selected", self._on_category_selected)
        lobby.whats_new_frame.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        # encoding is utf-8 (since r2218, see category.py)
        self.assertEqual(self._cat.name, 'What\xe2\x80\x99s New')
        self.assertEqual(self._cat.sortmode, SortMethods.BY_CATALOGED_TIME)

    def test_new_no_sort_info_yet(self):
        # ensure that we don't show a empty "whats new" category
        # see LP: #865985
        from softwarecenter.testutils import get_test_db
        db = get_test_db()
        cache = db._aptcache
        # simulate a fresh install with no catalogedtime info
        del db._axi_values["catalogedtime"]

        from softwarecenter.testutils import get_test_gtk3_icon_cache
        icons = get_test_gtk3_icon_cache()

        from softwarecenter.db.appfilter import AppFilter
        apps_filter = AppFilter(db, cache)

        from softwarecenter.distro import get_distro
        import softwarecenter.paths
        from softwarecenter.paths import APP_INSTALL_PATH
        from softwarecenter.ui.gtk3.views.catview_gtk import LobbyViewGtk
        view = LobbyViewGtk(softwarecenter.paths.datadir, APP_INSTALL_PATH,
                            cache, db, icons, get_distro(), apps_filter)
        view.show()

        # gui
        win = Gtk.Window()
        self.addCleanup(win.destroy)
        win.set_size_request(800, 400)

        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        scroll.show()
        win.add(scroll)
        win.show()
        # test visibility
        self._p()
        self.assertFalse(view.whats_new_frame.get_property("visible"))
        self._p()

    def test_recommended_for_you_opt_in_display(self):
        # patch the recommender UUID value to ensure that we are not opted-in
        # for this test
        recommender_opted_in_patcher = patch(
            'softwarecenter.backend.recagent.RecommenderAgent.is_opted_in')
        self.addCleanup(recommender_opted_in_patcher.stop)
        mock_get_recommender_opted_in = recommender_opted_in_patcher.start()
        mock_get_recommender_opted_in.return_value = False

        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)

        lobby = win.get_data("lobby")
        rec_panel = lobby.recommended_for_you_panel
        self._p()
        self.assertEqual(rec_panel.spinner_notebook.get_current_page(),
                         FramedHeaderBox.CONTENT)
        self.assertTrue(rec_panel.opt_in_vbox.get_property("visible"))

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recagent.RecommenderAgent'
           '.post_submit_profile')
    def test_recommended_for_you_spinner_display(self, mock_query):
        # patch the recommender UUID value to insure that we are not opted-in
        # for this test
        recommender_opted_in_patcher = patch(
            'softwarecenter.backend.recagent.RecommenderAgent.is_opted_in')
        self.addCleanup(recommender_opted_in_patcher.stop)
        mock_get_recommender_opted_in = recommender_opted_in_patcher.start()
        mock_get_recommender_opted_in.return_value = False

        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        lobby = win.get_data("lobby")
        rec_panel = lobby.recommended_for_you_panel
        self._p()
        # click the opt-in button to initiate the process,
        # this will show the spinner
        rec_panel.opt_in_button.emit('clicked')
        self._p()
        self.assertEqual(rec_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.SPINNER_PAGE)
        self.assertTrue(rec_panel.opt_in_vbox.get_property("visible"))

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recagent.RecommenderAgent'
           '.post_submit_profile')
    def test_recommended_for_you_display_recommendations(self,
            mock_query):
        # patch the recommender UUID value to insure that we are not opted-in
        # for this test
        recommender_opted_in_patcher = patch(
            'softwarecenter.backend.recagent.RecommenderAgent.is_opted_in')
        self.addCleanup(recommender_opted_in_patcher.stop)
        mock_get_recommender_opted_in = recommender_opted_in_patcher.start()
        mock_get_recommender_opted_in.return_value = False

        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        lobby = win.get_data("lobby")
        rec_panel = lobby.recommended_for_you_panel
        self._p()
        # click the opt-in button to initiate the process,
        # this will show the spinner
        rec_panel.opt_in_button.emit('clicked')
        self._p()
        rec_panel._update_recommended_for_you_content()
        self._p()
        # we fake the callback from the agent here
        for_you = lobby.recommended_for_you_panel.recommended_for_you_cat
        for_you._recommend_me_result(None,
            make_recommender_agent_recommend_me_dict())
        self.assertNotEqual(for_you.get_documents(self.db), [])
        self.assertEqual(rec_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.CONTENT_PAGE)
        self._p()
        # test clicking recommended_for_you More button
        lobby.connect("category-selected", self._on_category_selected)
        lobby.recommended_for_you_panel.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Recommended For You")

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recagent.RecommenderAgent'
           '.query_recommend_me')
    def test_recommended_for_you_display_recommendations_not_opted_in(self,
            mock_query):
        # patch the recommender UUID value to insure that we are not opted-in
        # for this test
        recommender_opted_in_patcher = patch(
            'softwarecenter.backend.recagent.RecommenderAgent.is_opted_in')
        self.addCleanup(recommender_opted_in_patcher.stop)
        mock_get_recommender_opted_in = recommender_opted_in_patcher.start()
        mock_get_recommender_opted_in.return_value = False

        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        # we want to work in the "subcat" view
        notebook = win.get_child()
        notebook.next_page()

        subcat_view = win.get_data("subcat")
        self._p()
        self.assertFalse(subcat_view.recommended_for_you_in_cat.get_property(
            "visible"))

    # patch out the agent query method to avoid making the actual server call
    @patch('softwarecenter.backend.recagent.RecommenderAgent'
           '.query_recommend_me')
    def test_recommended_for_you_display_recommendations_opted_in(self, mock_query):
        # patch the recommender UUID value to insure that we are not opted-in
        # for this test
        recommender_opted_in_patcher = patch(
            'softwarecenter.backend.recagent.RecommenderAgent.is_opted_in')
        self.addCleanup(recommender_opted_in_patcher.stop)
        mock_get_recommender_opted_in = recommender_opted_in_patcher.start()
        mock_get_recommender_opted_in.return_value = True

        # get the widgets we need
        win = get_test_window_catview()
        self.addCleanup(win.destroy)
        # we want to work in the "subcat" view
        notebook = win.get_child()
        notebook.next_page()

        subcat_view = win.get_data("subcat")
        rec_cat_panel = subcat_view.recommended_for_you_in_cat
        self._p()
        rec_cat_panel._update_recommended_for_you_content()
        self._p()
        # we fake the callback from the agent here
        rec_cat_panel.recommended_for_you_cat._recommend_me_result(
                                None,
                                make_recommender_agent_recommend_me_dict())
        result_docs = rec_cat_panel.recommended_for_you_cat.get_documents(
            self.db)
        self.assertNotEqual(result_docs, [])
        # check that we are getting the correct number of results,
        # corresponding to the following Internet items:
        #   Mangler, Midori, Midori Private Browsing, Psi
        self.assertTrue(len(result_docs) == 4)
        self.assertEqual(rec_cat_panel.spinner_notebook.get_current_page(),
                         SpinnerNotebook.CONTENT_PAGE)
        # check that the tiles themselves are visible
        self._p()
        self.assertTrue(rec_cat_panel.recommended_for_you_content.get_property(
            "visible"))
        self.assertTrue(rec_cat_panel.recommended_for_you_content.get_children(
            )[0].title.get_property("visible"))
        self._p()
        # test clicking recommended_for_you More button
        subcat_view.connect("category-selected", self._on_category_selected)
        rec_cat_panel.more.clicked()
        self._p()
        self.assertNotEqual(self._cat, None)
        self.assertEqual(self._cat.name, "Recommended For You in Internet")

    def _p(self):
        for i in range(5):
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()


class ExhibitsTestCase(unittest.TestCase):
    """The test suite for the exhibits carousel."""

    def setUp(self):
        self.datadir = softwarecenter.paths.datadir
        self.desktopdir = softwarecenter.paths.APP_INSTALL_PATH
        self.cache = FakedCache()
        self.db = StoreDatabase(cache=self.cache)
        self.lobby = catview_gtk.LobbyViewGtk(datadir=self.datadir,
            desktopdir=self.desktopdir, cache=self.cache, db=self.db,
            icons=None, apps_filter=None)
        self.addCleanup(self.lobby.destroy)

    def _get_banner_from_lobby(self):
        return self.lobby.vbox.get_children()[-1].get_child()

    def test_featured_exhibit_by_default(self):
        """Show the featured exhibit before querying the remote service."""
        self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIsInstance(banner.exhibits[0], catview_gtk.FeaturedExhibit)

    def test_no_exhibit_if_not_available(self):
        """The exhibit should not be shown if the package is not available."""
        exhibit = Mock()
        exhibit.package_names = u'foobarbaz'

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca, [exhibit])

        with patch.object(catview_gtk, 'SoftwareCenterAgent', lambda: sca):
            self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIsInstance(banner.exhibits[0], catview_gtk.FeaturedExhibit)

    def test_exhibit_if_available(self):
        """The exhibit should be shown if the package is not available."""
        exhibit = Mock()
        exhibit.package_names = u'foobarbaz'
        exhibit.banner_url = 'banner'

        pkg = Mock()
        pkg.banner_url = ''
        pkg.title_translated = ''
        self.cache[u'foobarbaz'] = pkg

        sca = ObjectWithSignals()
        sca.query_exhibits = lambda: sca.emit('exhibits', sca, [exhibit])

        with patch.object(catview_gtk, 'SoftwareCenterAgent', lambda: sca):
            self.lobby._append_banner_ads()

        banner = self._get_banner_from_lobby()
        self.assertEqual(1, len(banner.exhibits))
        self.assertIs(banner.exhibits[0], exhibit)


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
