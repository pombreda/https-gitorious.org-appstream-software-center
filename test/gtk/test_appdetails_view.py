#!/usr/bin/python

import logging

try:
    import mock
except ImportError:
    logging.error("please install the 'python-mock' package")
    raise
import gtk
import os
os.environ["SOFTWARE_CENTER_FAKE_REVIEW_API"] = "1"

import sys
import time
import unittest
import datetime

sys.path.insert(0,"../")
import softwarecenter.netstatus
import softwarecenter.paths

from softwarecenter.db.application import Application, AppDetails
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.distro import get_distro
from softwarecenter.enums import PkgStates
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.ui.gtk.appdetailsview_gtk import AppDetailsViewGtk
from softwarecenter.ui.gtk.widgets.reviews import EmbeddedMessage


class TestAppDetailsView(unittest.TestCase):
    """ tests the AppDetailsView """

    def setUp(self):
        # setup env/datadirs for the reviews helper
        datadir = "../data"
        softwarecenter.paths.datadir = datadir
        os.environ["PYTHONPATH"] = ".."
        # cache
        cache = get_pkg_info()
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
            db, distro, icons, cache, datadir, None)
        self.appdetails.show_all()

    def test_show_app_simple(self):
        app = Application("","2vcard")
        self.appdetails.show_app(app)
        self._p()
        self.assertFalse(self.appdetails.addon_view.get_property("visible"))

    def test_show_addons_bar(self):
        """ this tests if the addons bar is visible and also simulates
            a install to ensure that the "apply bar" goes away after
            a install/remove
        """
        app = Application("7zip", "p7zip-full")
        self.appdetails.show_app(app)
        self._p()
        self.assertTrue(
            self.appdetails.addon_view.get_property("visible"))
        # get first child
        widgets = self.appdetails.addon_view.get_children()
        # get the first addon, the widget layout is:
        #  first is the header, then the status bar, then all the addons
        addon = widgets[2]
        addon.checkbutton.set_active(not addon.checkbutton.get_active())
        self._p()
        self.assertTrue(
            self.appdetails.addons_statusbar.get_property("visible"))
        # simulate intall finished
        self.appdetails.addons_statusbar.applying = True
        result = mock.Mock()
        self.appdetails.backend.emit("transaction-finished", (None, result))
        self._p()
        self.assertFalse(
            self.appdetails.addons_statusbar.get_property("visible"))
        
    # DISABLED until failures are reliably fixed 
#    def test_show_app_simple_no_network(self):
#        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_DISCONNECTED
#        app = Application("Freeciv", "freeciv-client-gtk")
#        self.appdetails.show_app(app)
#        # this is async so we need to give it a bit of time
#        self._p()
#        time.sleep(1)
#        self._p()
#        for r in self.appdetails.reviews.vbox:
#            if self._is_embedded_message_no_network(r):
#                break
#        else:
#            raise Exception("can not find embedded message") 

    def test_show_app_simple_with_network(self):
        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_CONNECTED_OLD
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)
        # check that we do *not* have the embedded message
        for r in self.appdetails.reviews.vbox:
            self.assertFalse(self._is_embedded_message_no_network(r))

    def test_show_app_simple_network_unknown(self):
        # if we don't know about the network state (or have no network
        # manager running) assume connected 
        softwarecenter.netstatus.NETWORK_STATE = softwarecenter.netstatus.NetState.NM_STATE_UNKNOWN
        app = Application("7zip","p7zip-full")
        self.appdetails.show_app(app)
        # check that we do *not* have the embedded message
        for r in self.appdetails.reviews.vbox:
            self.assertFalse(self._is_embedded_message_no_network(r))

    def _is_embedded_message_no_network(self, message):
        return (isinstance(message, EmbeddedMessage) and
                message.image and
                message.image.get_icon_name()[0] == "network-offline")

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
        mock_app_details.purchase_date = None
        mock_app_details.installation_date = datetime.datetime.now()
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
        # make sure all PkgStates.* states work and do not cause crashes
        for i in range(PkgStates.UNKNOWN):
            mock_app_details.pkg_state = i
            if PkgStates.PURCHASED_BUT_REPO_MUST_BE_ENABLED:
                # for the purchased case, the value of purchase_date is a string
                mock_app_details.purchase_date = "2011-01-01 11:11:11"
            self.appdetails.show_app(app)

    def test_show_app_addons(self):
        app = Application("Web browser", "firefox")
        #mock_app_details = self._get_mock_app_details()
        self.appdetails.show_app(app)

    # DISABLED until failures are reliably fixed        
#    def test_enable_review_on_install(self):
#        app = Application("Freeciv", "freeciv-client-gtk")
#        mock_app_details = self._get_mock_app_details()
#        mock_app_details.pkg_state = PkgStates.UNINSTALLED
#        # monkey patch get_details() so that we get the mock object
#        app.get_details = lambda db: mock_app_details
#        self.appdetails.show_app(app)
#        # this is async so we need to give it a bit of time
#        self._p()
#        time.sleep(2)
#        self._p()
#        # check that the prompt to install the app to be able to review it is showing
#        self.assertFalse(self.appdetails.reviews.new_review.get_property("visible"))
#        self.assertTrue(self.appdetails.reviews.install_first_label.get_property("visible"))
#        # now simulate an install completed
#        self.appdetails.pkg_statusbar.pkg_state = PkgStates.INSTALLED
#        mock_app_details.pkg_state = PkgStates.INSTALLED
#        result = mock.Mock()
#        self.appdetails.backend.emit("transaction-finished", (None, result))
#        self._p()
#        time.sleep(2)
#        self._p()
#        # now that the app is installed, check that the invitation to review the app is showing
#        self.assertTrue(self.appdetails.reviews.new_review.get_property("visible"))

    # DISABLED until failures are reliably fixed 
#    def test_usefulness_submit_behaviour(self):
#        #set up fake review for expected behaviour
#        from softwarecenter.backend.fake_review_settings import FakeReviewSettings
#        fake_settings = FakeReviewSettings(True)
#        settings = {'fake_network_delay': 0, 'review_pages': 0, 'reviews_returned': 1,
#                    'votes_returned': 0, 'submit_usefulness_error': True}
#        fake_settings.update_multiple(settings)
#            
#        # needs to be inside a real window
#        win=gtk.Window()
#        scroll = gtk.ScrolledWindow()
#        scroll.add(self.appdetails)
#        win.add(scroll)
#        win.set_size_request(600,600)
#        win.show_all()
#        # build mock app
#        app = Application("3DChess", "3dchess")
#        mock_app_details = self._get_mock_app_details()
#        # monkey patch get_details() so that we get the mock object
#        app.get_details = lambda db: mock_app_details
#        self.appdetails.show_app(app)
#        self._p()
#        time.sleep(1)
#        self._p()
#        # and check the result
#        review_box = self.appdetails.reviews.vbox.get_children()[0]
#        self.assertTrue(review_box.useful.get_property('visible'))
#        self.assertFalse(review_box.submit_status_spinner.get_property('visible'))
#        self.assertTrue(review_box.yes_like.get_property('visible'))
#        review_box.yes_like.emit('clicked')
#        self._p()
#        time.sleep(2)
#        self._p()
#        #get the correct review_box again, since it's updated on callback
#        review_box = self.appdetails.reviews.vbox.get_children()[0]
#        self.assertTrue(review_box.submit_error_img.get_property('visible'))
#        self._p()
        
    
    # helper
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
