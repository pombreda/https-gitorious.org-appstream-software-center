#!/usr/bin/python

import sys
import unittest
sys.path.insert(0,"../")

from softwarecenter.utils import *

class TestSCUtils(unittest.TestCase):
    """ tests the sc utils """

    def test_encode(self):
        xml = "What&#x2019;s New"
        python = u"What\u2019s New"
        self.assertEqual(decode_xml_char_reference(xml), python)
        # fails currently 
        #self.assertEqual(encode_for_xml(python), xml)

    def test_lists_filename(self):
        debline = "deb http://foo:pass@security.ubuntu.com/ubuntu maverick-security main restricted"
        self.assertEqual(release_filename_in_lists_from_deb_line(debline),
                         "security.ubuntu.com_ubuntu_dists_maverick-security_Release")

    def test_get_http_proxy_from_libproxy(self):
        # test url
        url = "http://archive.ubuntu.com"
        # ensure we look at environment first
        os.environ["PX_CONFIG_ORDER"] = "config_envvar"
        # normal proxy
        os.environ["http_proxy"] = "http://localhost:3128/"
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "http://localhost:3128/")
        # direct
        os.environ["http_proxy"] = ""
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "")
        # user/pass
        os.environ["http_proxy"] = "http://user:pass@localhost:3128/"
        proxy = get_http_proxy_string_from_libproxy(url)
        self.assertEqual(proxy, "http://user:pass@localhost:3128/")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
