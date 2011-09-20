#!/usr/bin/python

from gi.repository import GObject

import os
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0,"../..")
sys.path.insert(0,"..")

# overwrite early
import softwarecenter.paths
softwarecenter.paths.datadir = "../data"

from softwarecenter.ui.gtk3.app import (
    SoftwareCenterAppGtk3)
from softwarecenter.ui.gtk3.panes.availablepane import (
    AvailablePane)

class TestPurchase(unittest.TestCase):

    def test_purchase_view_log_cleaner(self):
        import softwarecenter.ui.gtk3.views.purchaseview
        from softwarecenter.ui.gtk3.views.purchaseview import get_test_window_purchaseview
        win = get_test_window_purchaseview()
        self._p()
        # get the view
        view = win.get_data("view")
        # install the mock
        softwarecenter.ui.gtk3.views.purchaseview.LOG = mock = Mock()
        # run a "harmless" log message and ensure its logged normally
        view.wk.webkit.execute_script('console.log("foo")')
        self.assertTrue("foo" in mock.debug.call_args[0][0])
        mock.reset_mock()

        # run a message that contains token info
        s = 'http://sca.razorgirl.info/subscriptions/19077/checkout_complete/ @10: {"token_key": "hiddenXXXXXXXXXX", "consumer_secret": "hiddenXXXXXXXXXXXX", "api_version": 2.0, "subscription_id": 19077, "consumer_key": "rKhNPBw", "token_secret": "hiddenXXXXXXXXXXXXXXX"}'
        view.wk.webkit.execute_script("console.log('%s')" % s)
        self.assertTrue("skipping" in mock.debug.call_args[0][0])
        self.assertFalse("consumer_secret" in mock.debug.call_args[0][0])
        mock.reset_mock()
        
        # run another one
        win.destroy()


    def test_reinstall_previous_purchase_display(self):
        os.environ["PYTHONPATH"]=".."
        mock_options = Mock()
        mock_options.display_navlog = False
        mock_options.disable_apt_xapian_index = False
        mock_options.disable_buy = False
        xapiandb = "/var/cache/software-center/"
        app = SoftwareCenterAppGtk3(
            softwarecenter.paths.datadir, xapiandb, mock_options)
        app.window_main.show_all()
        app.available_pane.init_view()
        self._p()
        app.on_menuitem_reinstall_purchases_activate(None)
        # it can take a bit until the sso client is ready
        for i in range(100):
            if (app.available_pane.get_current_page() == 
                AvailablePane.Pages.LIST):
                break
            self._p()
        self.assertEqual(
            app.available_pane.get_current_page(), AvailablePane.Pages.LIST)

    def _p(self):
        context = GObject.main_context_default()
        for i in range(5):
            time.sleep(0.1)
            while context.pending():
                context.iteration()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
