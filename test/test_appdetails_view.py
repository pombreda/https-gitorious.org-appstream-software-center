#!/usr/bin/python

import logging
try:
    import mock
except ImportError:
    logging.error("please install the 'python-mock' package")
    raise
import gtk
import os
import sys
import time
import unittest

sys.path.insert(0,"../")
import softwarecenter.netstatus

from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.application import Application, AppDetails
from softwarecenter.distro import get_distro
from softwarecenter.enums import *
from softwarecenter.view.appdetailsview_gtk import AppDetailsViewGtk, EmbeddedMessage


class testAppDetailsView(unittest.TestCase):
    """ tests the AppDetailsView """

    def setUp(self):
        datadir = "../data"
        cache = AptCache()
        cache.open()
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        db = StoreDatabase(pathname, cache)
        db.open()
        distro = get_distro()
        # icon mock
        icons = gtk.icon_theme_get_default()
        # create a details object
        self.appdetails = AppDetailsViewGtk(
            db, distro, icons, cache, datadir)

    def test_show_app_simple(self):
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)

    def test_show_app_simple_no_network(self):
        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_DISCONNECTED
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)
        # check that we have the embedded message
        for r in self.appdetails.reviews.vbox:
            if isinstance(r, EmbeddedMessage):
                break
        else:
            raise Exception("can not find embedded message") 

    def test_show_app_simple_with_network(self):
        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_CONNECTED
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)
        # check that we do *not* have the embedded message
        for r in self.appdetails.reviews.vbox:
            self.assertFalse(isinstance(r, EmbeddedMessage))

    def test_show_app_simple_network_unknown(self):
        # if we don't know about the network state (or have no network
        # manager running) assume connected 
        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_UNKNOWN
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)
        # check that we do *not* have the embedded message
        for r in self.appdetails.reviews.vbox:
            self.assertFalse(isinstance(r, EmbeddedMessage))

    def _get_mock_app_details(self):
        mock_app_details = mock.Mock(AppDetails)
        mock_app_details.pkgname = "pkgname"
        mock_app_details.appname = "appname"
        mock_app_details.display_name = "display_name"
        mock_app_details.display_summary = "display_summary"
        mock_app_details.desktop_file = "firefox.desktop"
        mock_app_details.error = None
        mock_app_details.warning = None
        mock_app_details.description = "description"
        mock_app_details.website = "website"
        mock_app_details.thumbnail = None
        mock_app_details.license = "license"
        mock_app_details.maintenance_status = "support_status"
        mock_app_details.purchase_date = "purchase_date"
        mock_app_details.installation_date = "installation_date"
        mock_app_details.price = "price"
        mock_app_details.icon = "iconname"
        mock_app_details.icon_url = None
        mock_app_details.version = "1.0"
        # FIXME: this should vanish from the app_details
        mock_app_details._error_not_found = ""
        return mock_app_details

    def test_show_app_all_pkg_states(self):
        app = Application("7zip","p7zip-full")
        # create details mock
        mock_app_details = self._get_mock_app_details()
        # monkey patch get_details() so that we get the mock object
        app.get_details = lambda db: mock_app_details
        # make sure all PKG_STATE_* states work and do not cause crashes
        for i in range(PKG_STATE_UNKNOWN):
            mock_app_details.pkg_state = i
            self.appdetails.show_app(app)
    
    def test_show_app_addons(self):
        app = Application("Web browser", "firefox")
        mock_app_details = self._get_mock_app_details()
        self.appdetails.show_app(app)

    # helper
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
