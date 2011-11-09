#!/usr/bin/python

import unittest

import sys
sys.path.insert(0,"../")

import softwarecenter.paths
from softwarecenter.ui.gtk3.session.appmanager import (
    ApplicationManager, get_appmanager)
from softwarecenter.distro import get_distro
from softwarecenter.testutils import (
    get_test_db, get_test_install_backend, get_test_gtk3_icon_cache)

class TestAppManager(unittest.TestCase):
    """ tests the appmanager  """

    def test_get_appmanager(self):
        db = get_test_db()
        backend = get_test_install_backend()
        distro = get_distro()
        datadir = softwarecenter.paths.datadir
        icons = get_test_gtk3_icon_cache()
        app_manager = ApplicationManager(db, backend, distro, datadir, icons)
        self.assertNotEqual(app_manager, None)
        # test singleton
        app_manager2 = get_appmanager()
        self.assertEqual(app_manager, app_manager2)
        # test creating it twice
        




if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
