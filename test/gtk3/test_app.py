#!/usr/bin/python

import unittest
import xapian

from collections import defaultdict
from functools import partial

from testutils import do_events, get_mock_options, setup_test_env
setup_test_env()

import softwarecenter.paths

from softwarecenter.enums import PkgStates, SearchSeparators
from softwarecenter.ui.gtk3 import app


class AppTestCase(unittest.TestCase):
    """Test suite for the app module."""

    def setUp(self):
        super(AppTestCase, self).setUp()
        self.called = defaultdict(list)
        self.addCleanup(self.called.clear)

        datadir = softwarecenter.paths.datadir
        xapianpath = softwarecenter.paths.XAPIAN_BASE_PATH
        options = get_mock_options()
        self.app = app.SoftwareCenterAppGtk3(datadir, xapianpath, options)
        self.addCleanup(self.app.destroy)

        self.app.cache.open()

    def track_calls(self, signal_name, *a, **kw):
        """Record the callback for 'signal_name' using 'args' and 'kwargs'."""
        self.called[signal_name].append((a, kw))


class ShowAvailablePackagesTestCase(AppTestCase):
    """Test suite for parsing and loading package lists."""

    installed = False
    prefix = 'apt:'

    def setUp(self):
        super(ShowAvailablePackagesTestCase, self).setUp()
        # connect some signals of interest
        self.app.installed_pane.connect('installed-pane-created',
            partial(self.track_calls, 'installed-pane-created'))
        self.app.available_pane.connect('available-pane-created',
            partial(self.track_calls, 'available-pane-created'))

    def check_available_pane_shown(self, apps=None):
        """Check that the available_pane was shown."""
        expected = [((self.app.available_pane,), {})]
        self.assertEqual(self.called, {'available-pane-created': expected})

        if apps and len(apps) == 1:
            app_name, = apps
            self.assertEqual(app_name,
                self.app.available_pane.app_details_view.app_details.name)
        else:
            self.assertIsNone(
                self.app.available_pane.app_details_view.app_details)

        if apps and len(apps) > 1:
            self.assertEqual(SearchSeparators.PACKAGE.join(apps),
                self.app.available_pane.searchentry.get_text())
        else:
            self.assertEqual('',
                self.app.available_pane.searchentry.get_text())

    def test_empty_string(self):
        """Pass an empty string, show the 'available' view."""
        self.app.show_available_packages('')

        self.check_available_pane_shown()

    def test_non_empty_string(self):
        """Pass a non empty string, show the 'available' view."""
        self.app.show_available_packages('foo')
        self.check_available_pane_shown(apps=('foo',))

    def test_non_empty_string_with_package_separator(self):
        """Pass a string with the package sep, show the 'available' view."""
        self.app.show_available_packages('foo,bar')
        self.check_available_pane_shown(apps=('foo', 'bar'))

    def test_empty_sequence(self):
        """Pass an empty sequence, show the 'available' view."""
        self.app.show_available_packages(())
        self.check_available_pane_shown()

    def test_one_package(self):
        """Pass one package, show the 'available' view."""
        apps = ('foo',)
        self.app.show_available_packages(apps)
        self.check_available_pane_shown(apps)

        self.assertEqual(PkgStates.NOT_FOUND,
            self.app.available_pane.app_details_view.app_details.pkg_state)

    def test_two_packages(self):
        """Pass two packages, show the 'available' view."""
        apps = ('foo', 'bar')
        self.app.show_available_packages(apps)
        self.check_available_pane_shown(apps)

    def _test_with_invalid_package_prefix(self):
        """Pass a package with an invalid package prefix."""
        apps = ('apt:/foo',)
        self.app.show_available_packages(apps)
        self.check_available_pane_shown(apps)

    def _test_with_package_prefix(self):
        """Pass a package with the package prefix."""
        for case in ('foo',):  # 'apt:foo', 'apt://foo', 'apt:///foo'):
            self.app.show_available_packages((self.prefix + case,))
            self.check_available_pane_shown(apps=(case,))

            self.assertEqual(PkgStates.NOT_FOUND,
                self.app.available_pane.app_details_view.app_details.pkg_state)


    # search:magicicada thunderbird firefox -> search for "magicicada thunderbird firefox"
    # magicicada thunderbird firefox -> search for "magicicada,thunderbird,firefox"
    # search:magicicada apt:thunderbird,firefox -> search for "magicicada apt:thunderbird firefox"
    # search:magicicada, apt:thunderbird firefox -> search for "thunderbird,firefox,search:magicicada,"

    # apt:magicicada,firefox,thunderbird -> "magicicada,firefox,thunderbird"
    # apt:magicicada,apt:firefox,apt:thunderbird -> "magicicada,apt:firefox,apt:thunderbird"

    # /home/nessita/poll.py -> ValueError: Need a deb file, got '/home/nessita/poll.py'
    # apt:/home/nessita/poll.py -> ValueError: Need a deb file, got '/home/nessita/poll.py'
    # search:/home/nessita/poll.py -> search for "/home/nessita/poll.py"
    # search:apt:/home/nessita/poll.py -> search for "apt:/home/nessita/poll.py"


class __ShowAvailablePackagesTwoSlashesTestCase(ShowAvailablePackagesTestCase):
    """Test suite for parsing and loading package lists."""

    prefix = 'apt://'


class __ShowAvailablePackagesThreeSlashesTestCase(ShowAvailablePackagesTestCase):
    """Test suite for parsing and loading package lists."""

    prefix = 'apt:///'


if __name__ == "__main__":
    unittest.main()
