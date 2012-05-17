import os
import unittest

from gi.repository import Gtk

from softwarecenter.enums import SOFTWARE_CENTER_DEBUG_TABS
from softwarecenter.ui.gtk3.widgets import SpinnerNotebook


class SpinnerNotebookTestCase(unittest.TestCase):
    """The test case for the SpinnerNotebook."""

    def setUp(self):
        self.content = Gtk.Label('My test')
        self.obj = SpinnerNotebook(self.content)
        self.addCleanup(self.obj.hide)
        self.addCleanup(self.obj.destroy)
        assert SOFTWARE_CENTER_DEBUG_TABS not in os.environ

        self.obj.show()

    def test_no_borders(self):
        """The notebook has no borders."""
        self.assertFalse(self.obj.get_show_borders())

    def test_no_tabs(self):
        """The notebook has no visible tabs."""
        self.assertFalse(self.obj.get_show_tabs())

    def test_tabs_if_debug_set(self):
        """The notebook has visible tabs if debug is set."""
        os.environ
        self.assertFalse(self.obj.get_show_tabs())

    def test_has_two_pages(self):
        """The notebook has two pages."""
        self.assertEqual(self.obj.get_n_pages(), 2)

    def test_has_content(self):
        """The notebook has the given content."""
        self.assertEqual(self.obj.get_page(self.obj.CONTENT_PAGE),
                         self.content)

    def test_has_spinner(self):
        """The notebook has the spinner view."""
        self.assertEqual(self.obj.get_page(self.obj.SPINNER_PAGE),
                         self.obj.spinner_view)
        self.assertTrue(self.obj.spinner_view.get_visible())


if __name__ == "__main__":
    unittest.main()
