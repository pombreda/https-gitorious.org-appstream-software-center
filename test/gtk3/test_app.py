#!/usr/bin/python

import unittest

from collections import defaultdict
from functools import partial

from testutils import get_mock_options, setup_test_env
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

        orig = app.SoftwareCenterAppGtk3.START_DBUS
        self.addCleanup(setattr, app.SoftwareCenterAppGtk3, 'START_DBUS', orig)
        app.SoftwareCenterAppGtk3.START_DBUS = False

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

    def setUp(self):
        super(ShowAvailablePackagesTestCase, self).setUp()
        # connect some signals of interest
        cid = self.app.installed_pane.connect('installed-pane-created',
                partial(self.track_calls, 'installed-pane-created'))
        self.addCleanup(self.app.installed_pane.disconnect, cid)
        cid = self.app.available_pane.connect('available-pane-created',
                partial(self.track_calls, 'available-pane-created'))
        self.addCleanup(self.app.available_pane.disconnect, cid)

    def transform_for_test(self, items):
        """Do nothing, children will do interesting things."""
        return items

    def check_available_pane_shown(self, apps, items=None):
        """Check that the available_pane was shown."""
        if items is None:
            items = self.transform_for_test(apps)

        self.app.show_available_packages(items)

        expected = [((self.app.available_pane,), {})]
        self.assertEqual(self.called, {'available-pane-created': expected})

        if apps and len(apps) == 1 and apps[0]:
            app_name, = apps
            self.assertEqual(app_name,
                self.app.available_pane.app_details_view.app_details.name)
            self.assertEqual(PkgStates.NOT_FOUND,
                self.app.available_pane.app_details_view.app_details.pkg_state)
        else:
            self.assertIsNone(
                self.app.available_pane.app_details_view.app_details)

        if apps and len(apps) > 1:
            self.assertEqual(SearchSeparators.PACKAGE.join(apps),
                self.app.available_pane.searchentry.get_text())
        else:
            self.assertEqual('',
                self.app.available_pane.searchentry.get_text())

    def test_empty(self):
        """Pass an empty argument, show the 'available' view."""
        self.check_available_pane_shown(apps=())

    def test_single_empty_item(self):
        """Pass a single empty item, show the 'available' view."""
        self.check_available_pane_shown(apps=('',))

    def test_single_item(self):
        """Pass a single item, show the 'available' view."""
        self.check_available_pane_shown(apps=('foo',))

    def test_two_items(self):
        """Pass two items, show the 'available' view."""
        self.check_available_pane_shown(apps=('foo', 'bar'))

    def test_item_with_invalid_prefix(self):
        """Pass a item with an invalid item prefix."""
        # something in the Application construction layer is removing the
        # expected '/' in the item name
        self.check_available_pane_shown(apps=('foo',), items=('apt:/foo',))

    def test_item_with_prefix(self):
        """Pass a item with the item prefix."""
        for prefix in ('apt:', 'apt://', 'apt:///'):
            for case in ('foo', 'apt:foo'):
                self.check_available_pane_shown(apps=(case,),
                                                items=(prefix + case,))

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


class ShowAvailablePackagesFromStringTestCase(ShowAvailablePackagesTestCase):
    """Test suite for parsing and loading package lists."""

    def transform_for_test(self, items):
        """Transform a sequence into a comma separated string."""
        return ','.join(items)


if __name__ == "__main__":
    unittest.main()
