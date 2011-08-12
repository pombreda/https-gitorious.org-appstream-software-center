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
        for i in range(50):
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
