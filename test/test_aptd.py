#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import unittest

from softwarecenter.backend.aptd import AptdaemonBackend
from softwarecenter.enums import *

class testAptdaemon(unittest.TestCase):
    """ tests the AptdaemonBackend """

    def setUp(self):
        self.aptd = AptdaemonBackend()
        # monkey patch 
        self.aptd.aptd_client.install_packages = self._mock_aptd_client_install_packages
        self._pkgs_to_install = []
    
    def _mock_aptd_client_install_packages(self, pkgs, reply_handler, error_handler):
        self._pkgs_to_install.extend(pkgs)

    def test_install_multiple(self):
        # FIXME: this test is not great, it should really 
        #        test that there are multiple transactions, that the icons
        #        are correct etc - that needs some work in order to figure
        #        out how to best do that with aptdaemon/aptd.py
        pkgnames = ["7zip", "2vcard"]
        appnames = ["The 7 zip app", ""]
        iconnames = ["icon-7zip", ""]
        self.aptd.install_multiple(pkgnames, appnames, iconnames)
        self.assertEqual(self._pkgs_to_install, ["7zip", "2vcard"])
        self._pkgs_to_install = []

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
