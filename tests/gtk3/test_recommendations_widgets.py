import unittest

from tests.utils import setup_test_env
setup_test_env()

from tests.gtk3.windows import get_test_window_recommendations


# FIXME: the code from test_catview that tests the lobby widget should
#        move here as it should be fine to test it in isolation

class TestRecommendationsWidgets(unittest.TestCase):

    def test_recommendations_lobby(self):
        win = get_test_window_recommendations(panel_type="lobby")
        self.addCleanup(win.destroy)

    def test_recommendations_category(self):
        win = get_test_window_recommendations(panel_type="category")
        self.addCleanup(win.destroy)

    def test_recommendations_details(self):
        win = get_test_window_recommendations(panel_type="details")
        self.addCleanup(win.destroy)


if __name__ == "__main__":
    unittest.main()
