#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import unittest

from softwarecenter.backend.aptd import AptdaemonBackend
from softwarecenter.enums import *

class TestAptdaemon(unittest.TestCase):
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
        # need to yiel as install_multiple is a inline_callback (generator)
        yield self.aptd.install_multiple(pkgnames, appnames, iconnames)
        self.assertEqual(self._pkgs_to_install, ["7zip", "2vcard"])
        self._pkgs_to_install = []

    def _monkey_patched_add_vendor_key_from_keyserver(self, keyid, keyserver):
        self.assertTrue(keyid.startswith("0x"))

    def test_download_key_from_keyserver(self):
        keyid = "0EB12F05"
        keyserver = "keyserver.ubuntu.com"
        self.aptd.aptd_client.add_vendor_key_from_keyserver = self._monkey_patched_add_vendor_key_from_keyserver
        self.aptd.add_vendor_key_from_keyserver(keyid, keyserver)
        
    def test_apply_changes(self):
        pkgname = "gimp"
        appname = "The GIMP app"
        iconname = "icon-gimp"
        addons_install = ["gimp-data-extras", "gimp-gutenprint"]
        addons_remove = ["gimp-plugin-registry"]
        yield self.aptd.apply_changes(pkgname, appname ,iconname, addons_install, addons_remove)

    def test_simulate(self):
        print "sim"
        res = self.aptd.simulate_remove_multiple(["2vcard"])
        print "lala", res.result

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
