#!/usr/bin/python

import os
import unittest

from collections import defaultdict
from functools import partial

from mock import Mock

from testutils import do_events, get_mock_options, setup_test_env
setup_test_env()

import softwarecenter.paths

from softwarecenter.enums import PkgStates, SearchSeparators
from softwarecenter.ui.gtk3 import app


class FakedCache(dict):
    """A faked cache."""

    def __init__(self, *a, **kw):
        super(FakedCache, self).__init__()
        self._callbacks = defaultdict(list)
        self.ready = False

    def open(self):
        """Open this cache."""
        self.ready = True

    def connect(self, signal, callback):
        """Connect a signal with a callback."""
        self._callbacks[signal].append(callback)

    def disconnect_by_func(self, callback):
        """Disconnect 'callback' from every signal."""
        for signal, cb in self._callbacks.iteritems():
            if cb == callback:
                self._callbacks[signal].remove(callback)
            if len(self._callbacks[signal]) == 0:
                self._callbacks.pop(signal)

    def get_addons(self, pkgname):
        """Return (recommended, suggested) addons for 'pkgname'."""
        return ([],[])

    def get_total_size_on_install(self,pkgname, addons_to_install,
                                  addons_to_remove, archive_suite):
        """Return a fake (total_download_size, total_install_size) result."""
        return (0, 0)


class AppTestCase(unittest.TestCase):
    """Test suite for the app module."""

    def setUp(self):
        super(AppTestCase, self).setUp()
        self.called = defaultdict(list)
        self.addCleanup(self.called.clear)

        orig = app.SoftwareCenterAppGtk3.START_DBUS
        self.addCleanup(setattr, app.SoftwareCenterAppGtk3, 'START_DBUS', orig)
        app.SoftwareCenterAppGtk3.START_DBUS = False

        orig = app.get_pkg_info
        self.addCleanup(setattr, app, 'get_pkg_info', orig)
        app.get_pkg_info = lambda: FakedCache()

        datadir = softwarecenter.paths.datadir
        xapianpath = softwarecenter.paths.XAPIAN_BASE_PATH
        options = get_mock_options()
        self.app = app.SoftwareCenterAppGtk3(datadir, xapianpath, options)
        self.addCleanup(self.app.destroy)

        self.app.cache.open()

    def track_calls(self, signal_name, *a, **kw):
        """Record the callback for 'signal_name' using 'args' and 'kwargs'."""
        self.called[signal_name].append((a, kw))


class ShowPackagesTestCase(AppTestCase):
    """Test suite for parsing/searching/loading package lists."""

    pkg_name = 'foo'

    def setUp(self):
        super(ShowPackagesTestCase, self).setUp()
        # connect some signals of interest
        cid = self.app.installed_pane.connect('installed-pane-created',
                partial(self.track_calls, 'pane-created'))
        self.addCleanup(self.app.installed_pane.disconnect, cid)

        cid = self.app.available_pane.connect('available-pane-created',
                partial(self.track_calls, 'pane-created'))
        self.addCleanup(self.app.available_pane.disconnect, cid)

    def transform_for_test(self, items):
        """Transform a sequence into a comma separated string."""
        return app.SEARCH_PREFIX + SearchSeparators.REGULAR.join(items)

    def do_check(self, apps, items=None):
        """Check that the available_pane was shown."""
        if items is None:
            items = self.transform_for_test(apps)

        self.app.show_available_packages(items)

        expected = [((self.app.available_pane,), {})]
        self.assertEqual(self.called, {'pane-created': expected})

        self.assertEqual(SearchSeparators.REGULAR.join(apps),
            self.app.available_pane.searchentry.get_text())
        self.assertIsNone(
            self.app.available_pane.app_details_view.app_details)

    def test_empty(self):
        """Pass an empty argument, show the 'available' view."""
        self.do_check(apps=())

    def test_single_empty_item(self):
        """Pass a single empty item, show the 'available' view."""
        self.do_check(apps=('',))

    def test_single_item(self):
        """Pass a single item, show the 'available' view."""
        self.do_check(apps=(self.pkg_name,))

    def test_two_items(self):
        """Pass two items, show the 'available' view."""
        self.do_check(apps=(self.pkg_name, 'bar'))

    def test_several_items(self):
        """Pass several items, show the 'available' view."""
        self.do_check(apps=(self.pkg_name, 'firefox', 'software-center'))

    def test_item_is_a_file(self):
        """Pass an item that is an existing file."""
        fname = __file__
        assert os.path.exists(fname)
        self.do_check(apps=(os.path.abspath(fname),), items=(fname,))


class ShowPackagesAptTestCase(ShowPackagesTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = None

    def setUp(self):
        super(ShowPackagesAptTestCase, self).setUp()
        assert self.pkg_name not in self.app.cache
        if self.installed is not None:
            mock_cache_entry = Mock()
            mock_cache_entry.website = None
            mock_cache_entry.license = None
            mock_cache_entry.installed_files = []
            mock_cache_entry.candidate = Mock()
            mock_cache_entry.candidate.version = '1.0'
            mock_cache_entry.candidate.description = 'A nonsense app.'
            mock_cache_entry.candidate.origins = ()
            mock_cache_entry.versions = (Mock(),)
            mock_cache_entry.versions[0].version = '0.99'
            mock_cache_entry.versions[0].origins = (Mock(),)
            mock_cache_entry.versions[0].origins[0].archive = 'test'
            mock_cache_entry.is_installed = self.installed
            if self.installed:
                mock_cache_entry.installed = Mock()
                mock_cache_entry.installed.version = '0.90'
                mock_cache_entry.installed.installed_size = 0
            else:
                mock_cache_entry.installed = None

            self.app.cache[self.pkg_name] = mock_cache_entry
            self.addCleanup(self.app.cache.pop, self.pkg_name)

    def transform_for_test(self, items):
        """Do nothing, children will do interesting things."""
        return items

    def check_package_availability(self, name):
        """Check whether the package 'name' is available."""
        pane = self.app.available_pane
        if name not in self.app.cache:
            state = PkgStates.NOT_FOUND
        elif self.app.cache[name].installed:
            state = PkgStates.INSTALLED
            pane = self.app.installed_pane
        else:
            state = PkgStates.UNINSTALLED

        self.assertEqual(state, pane.app_details_view.app_details.pkg_state)

        return pane

    def do_check(self, apps, items=None):
        """Check that the available_pane was shown."""
        if items is None:
            items = self.transform_for_test(apps)

        self.app.show_available_packages(items)

        expected_pane = self.app.available_pane
        if apps and len(apps) == 1 and apps[0] and not os.path.isfile(apps[0]):
            app_name, = apps
            expected_pane = self.check_package_availability(app_name)
            name = expected_pane.app_details_view.app_details.name
            self.assertEqual(app_name, name)
        else:
            self.assertIsNone(
                self.app.available_pane.app_details_view.app_details)

        if apps and (len(apps) > 1 or os.path.isfile(apps[0])):
            self.assertEqual(SearchSeparators.PACKAGE.join(apps),
                self.app.available_pane.searchentry.get_text())
        else:
            self.assertEqual('',
                self.app.available_pane.searchentry.get_text())

        self.assertEqual(self.called,
            {'pane-created': [((expected_pane,), {})]},
            'Pane is not correct for args %r (got %r).' % (items, self.called))

    def test_item_with_prefix(self):
        """Pass a item with the item prefix."""
        for prefix in ('apt:', 'apt://', 'apt:///'):
            for case in (self.pkg_name, app.PACKAGE_PREFIX + self.pkg_name):
                self.do_check(apps=(case,), items=(prefix + case,))


class ShowPackagesNotInstalledTestCase(ShowPackagesAptTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = False


class ShowPackagesInstalledTestCase(ShowPackagesAptTestCase):
    """Test suite for parsing/searching/loading package lists."""

    installed = True


class ShowPackagesStringTestCase(ShowPackagesAptTestCase):
    """Test suite for parsing/loading package lists from strings."""

    def transform_for_test(self, items):
        """Transform a sequence into a comma separated string."""
        return SearchSeparators.PACKAGE.join(items)


if __name__ == "__main__":
    unittest.main()
