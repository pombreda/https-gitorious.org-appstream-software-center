#!/usr/bin/python

import unittest
import xapian

from collections import defaultdict
from functools import partial

from testutils import do_events, get_mock_options, setup_test_env
setup_test_env()

import softwarecenter.paths

from softwarecenter.ui.gtk3 import app


class AppTestCase(unittest.TestCase):
    """Test suite for the app module."""

    def setUp(self):
        print '\n\n\n================================================== START'
        super(AppTestCase, self).setUp()
        self.called = defaultdict(list)
        self.addCleanup(self.called.clear)

        datadir = softwarecenter.paths.datadir
        xapianpath = softwarecenter.paths.XAPIAN_BASE_PATH
        options = get_mock_options()
        self.app = app.SoftwareCenterAppGtk3(datadir, xapianpath, options)
        self.addCleanup(self.app.destroy)

        self.app.cache.open()

    def tearDown(self):
        super(AppTestCase, self).tearDown()
        print '\n\n\n================================================== END'

    def track_calls(self, signal_name, *a, **kw):
        """Record the callback for 'signal_name' using 'args' and 'kwargs'."""
        self.called[signal_name].append((a, kw))


class ShowAvailablePackagesTestCase(AppTestCase):
    """Test suite for parsing and loading package lists."""

    sequence_builder = tuple
    installed = False

    def setUp(self):
        super(ShowAvailablePackagesTestCase, self).setUp()

        # connect some signals of interest
        #self.app.view_manager.connect('view-changed',
        #    partial(self.track_calls, 'view-changed'))
        self.app.installed_pane.connect('installed-pane-created',
            partial(self.track_calls, 'installed-pane-created'))
        self.app.available_pane.connect('available-pane-created',
            partial(self.track_calls, 'available-pane-created'))

    def check_available_pane_shown(self, app_name=None):
        """Check that the available_pane was shown."""
        expected = [((self.app.available_pane,), {})]
        self.assertEqual(self.called, {'available-pane-created': expected})

        if app_name is not None:
            self.assertEqual(app_name,
                self.app.available_pane.app_details_view.app_details.name)

    def _test_empty_string(self):
        """Pass an empty string, show the regular 'available' view."""
        self.app.show_available_packages('')

        expected = (self.app.view_manager, app.ViewPages.AVAILABLE)
        self.assertEqual(self.called, {'view-changed': [(expected, {})]})

    def _test_non_empty_string(self):
        """Pass a non empty string, show the regular 'available' view."""
        self.app.show_available_packages('foo')

        expected = (self.app.view_manager, app.ViewPages.AVAILABLE)
        self.assertEqual(self.called, {'view-changed': [(expected, {})]})

    def _test_empty_sequence(self):
        """Pass an empty sequence, show the regular 'available' view."""
        self.app.show_available_packages(())
        self.check_available_pane_shown()

    def test_one_item_in_sequence(self):
        """Pass a sequence with one package, show the regular 'available' view."""
        self.app.show_available_packages(('foo',))
        do_events()
        import time; time.sleep(1)
        do_events()
        self.check_available_pane_shown(app_name='foo')

        from softwarecenter.enums import PkgStates
        self.assertEqual(PkgStates.NOT_FOUND,
            self.app.available_pane.app_details_view.app_details.pkg_state)


if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
