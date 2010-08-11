#!/usr/bin/python

import glib
import os
import sys
import time
import unittest

from mock import Mock

sys.path.insert(0,"../")
from softwarecenter.distro.Ubuntu import Ubuntu

class MockCache(object):
    def __init__(self, mock_base_url):
        self._baseurl = mock_base_url
    
    def __getitem__(self, k):
        return MockPackage(self, k)

class MockPackage(object):
    def __init__(self, parent, pkgname):
        self._parentcache = parent
        self.name = pkgname
    @property
    def candidate(self):
        return MockVersion(self)

class MockVersion(object):
    def __init__(self, parent, version="1.0"):
        self._parentpkg = parent
        self._version = version
    @property
    def uri(self):
        pkgname = self._parentpkg.name
        baseurl = self._parentpkg._parentcache._baseurl
        return "%s/pool/main/%s/%s/%s_%s_all.deb" % (
            baseurl, pkgname[0], pkgname, pkgname, self._version)
                                                     

class TestDistroUbuntu(unittest.TestCase):

    def setUp(self):
        self.distro = Ubuntu()

    def test_icon_download_url(self):
        mock_cache = MockCache("http://ppa.launchpad.net/mvo/ppa/ubuntu")
        pkgname = "pkg"
        iconname = "iconfilename"
        icon_url = self.distro.get_downloadable_icon_url(mock_cache, pkgname, iconname)
        self.assertEqual(icon_url,
                         "http://ppa.launchpad.net/mvo/meta/ppa/iconfilename")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()