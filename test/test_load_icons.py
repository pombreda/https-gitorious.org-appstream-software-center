#!/usr/bin/python


import sys
import unittest

from mock import Mock

sys.path.insert(0,"../")
from softwarecenter.app import SoftwareCenterApp
from softwarecenter.paths import XAPIAN_BASE_PATH

class TestIconLoader(unittest.TestCase):
    """ tests the sc utils """

    def test_icons_loading(self):
        """ this test goes over the database and tries to load the icons
            to count how many are missing
        """
        mock_options = Mock()
        mock_options.enable_lp = False
        mock_options.enable_buy = True
        self.app = SoftwareCenterApp("../data", XAPIAN_BASE_PATH, mock_options)
        self.app.db.open()
        fail = icons = 0
        for (i, doc) in enumerate(self.app.db):
            iconname = self.app.db.get_iconname(doc)
            if not iconname:
                continue
            icons += 1
            if not self.app.icons.has_icon(iconname):
                fail += 1
        print "icons total: %s missing: %s" % (icons, fail)
        # pretty arbitrary test, just ensure we load "enough", current
        # natty from 2011-04-13 has 2226 icons and 584 missing
        self.assertTrue(fail < icons/2)

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
