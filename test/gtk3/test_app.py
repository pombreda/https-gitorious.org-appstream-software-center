#!/usr/bin/python

import unittest
import xapian

from collections import defaultdict
from functools import partial

from testutils import get_mock_options, setup_test_env
setup_test_env()

import softwarecenter.paths

from softwarecenter.ui.gtk3 import app


class AppTestCase(unittest.TestCase):
    """Test suite for the app module."""

    def setUp(self):
        super(AppTestCase, self).setUp()
        #self.cache = get_test_pkg_info()
        #self.icons = get_test_gtk3_icon_cache()
        #self.db = get_test_db()

        self.called = defaultdict(list)

        datadir = softwarecenter.paths.datadir
        xapianpath = softwarecenter.paths.XAPIAN_BASE_PATH
        options = get_mock_options()
        self.app = app.SoftwareCenterAppGtk3(datadir, xapianpath, options)
        self.addCleanup(self.app.window_main.destroy)
        self.app.run(args=[])

    def track_calls(self, signal_name, *a, **kw):
        """Record the callback for 'signal_name' using 'args' and 'kwargs'."""
        self.called[signal_name].append((a, kw))


class LoadAptPackageListTestCase(AppTestCase):
    """Tets suite for parsing and loading packge lists."""

    sequence_builder = tuple

    def setUp(self):
        super(LoadAptPackageListTestCase, self).setUp()
        # connect some signals of interest
        self.app.view_manager.connect('view-changed',
            partial(self.track_calls, 'view-changed'))
        self.app.available_pane.connect('available-pane-created',
            partial(self.track_calls, 'available-pane-created'))

    def test_empty_string(self):
        """Pass an empty string, show the regular 'available' view."""
        self.app.show_available_packages('')

        expected = (self.app.view_manager, app.ViewPages.AVAILABLE)
        self.assertEqual(self.called, {'view-changed': [(expected, {})]})

    def test_non_empty_string(self):
        """Pass a non empty string, show the regular 'available' view."""
        self.app.show_available_packages('foo')

        expected = (self.app.view_manager, app.ViewPages.AVAILABLE)
        self.assertEqual(self.called, {'view-changed': [(expected, {})]})

    def test_empty_sequence(self):
        """Pass an empty sequence, show the regular 'available' view."""
        self.app.show_available_packages(self.sequence_builder())

        expected = (self.app.view_manager, app.ViewPages.AVAILABLE)
        self.assertEqual(self.called, {'view-changed': [(expected, {})]})


if __name__ == "__main__":
    unittest.main()
