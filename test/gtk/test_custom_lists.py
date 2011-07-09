#!/usr/bin/python

import apt
import gtk
import logging
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0, "..")

from softwarecenter.ui.gtk.app import SoftwareCenterApp
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.ui.gtk.appview import AppStore

# see https://wiki.ubuntu.com/SoftwareCenter/SearchTesting

class TestCustomLists(unittest.TestCase):
    
    def _p(self):
        while gtk.events_pending():
            gtk.main_iteration()

    def setUp(self):
        # options
        mock_options = Mock()
        mock_options.enable_lp = False
        mock_options.enable_buy = True
        apt.apt_pkg.config.set("Dir::log::history", "/tmp")
        apt.apt_pkg.config.set("Dir::state::lists", "/tmp")
        self.app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
        self.app.window_main.show_all()
        print "foo0"
        self._p()
        print "foo1"

    def _run_search(self, search_text):
        logging.info("_run_search", search_text)
        self.app.available_pane.searchentry.delete_text(0, -1)
        self.app.available_pane.searchentry.insert_text(search_text)
        self._p()
        time.sleep(2)
        self._p()
        return self.app.available_pane.app_view.get_model()
        
    def _debug(self, index, model, needle):
        print "Expected '%s' at index '%s', and custom list contained: '%s'" % (needle, index, model[index][AppStore.COL_PKGNAME])

    def assertPkgInListAtIndex(self, index, model, needle):
        self.assertEqual(model[index][AppStore.COL_PKGNAME], 
                         needle, self._debug(index, model, needle))

    def test_custom_lists(self):
        # assert we generate the correct custom list
        model = self._run_search("ark,artha,software-center")
        self.assertPkgInListAtIndex(0, model, "ark")
        self.assertPkgInListAtIndex(1, model, "artha")
        self.assertPkgInListAtIndex(2, model, "software-center")
        
        # check that the "Custom List" button appears in the navigation bar
        self.assertEqual(
            str(self.app.available_pane.navigation_bar.get_parts()),
            "[Get Software, Custom List]")
        
        # check that the status bar indicates the correct number of packages
        # in the list
        status_bar_text = self.app.label_status.get_text()
        self.assertTrue(status_bar_text.startswith("3"))
        
        # TODO: test action bar functionality

if __name__ == "__main__":
    unittest.main()
