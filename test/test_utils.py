#!/usr/bin/python

import os
import datetime
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.utils import (decode_xml_char_reference,
                                  release_filename_in_lists_from_deb_line,
                                  get_http_proxy_string_from_libproxy,
                                  get_region,
                                  )


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

    def test_get_http_proxy_from_gsettings(self):
        from softwarecenter.utils import get_http_proxy_string_from_gsettings
        # FIXME: do something more meaningful here once I figured out
        #        how to create a private fake gsettings
        proxy = get_http_proxy_string_from_gsettings()
        self.assertTrue(type(proxy) in [type(None), type("")])

    # disabled, we don't use libproxy currently, its really rather
    # out of date
    def disabled_test_get_http_proxy_from_libproxy(self):
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

    def test_get_title_from_html(self):
        from softwarecenter.utils import get_title_from_html
        html = """
<html>
<head>
<title>Title &amp; text</title>
</head>
<body>
 <h1>header1</h1>
</body>
</html>"""
        # get the title from the html
        self.assertEqual(get_title_from_html(html),
                         "Title & text")
        # fallback to the first h1 if there is no title
        html = "<body><h1>foo &gt;</h1><h1>bar</h1></body>"
        self.assertEqual(get_title_from_html(html), "foo >")
        # broken
        html = "<sadfsa>dsf"
        self.assertEqual(get_title_from_html(html),
                         "")
        # not supported to have sub-html tags in the extractor
        html = "<body><h1>foo <emph>bar</emph></h1></body>"
        self.assertEqual(get_title_from_html(html),
                         "")
        html = "<body><h1>foo <emph>bar</emph> x</h1><h2>some text</h2></body>"
        self.assertEqual(get_title_from_html(html),
                         "")

    def test_no_display_desktop_file(self):
        from softwarecenter.utils import is_no_display_desktop_file
        d = "/usr/share/app-install/desktop/wine1.3:wine.desktop"
        self.assertTrue(is_no_display_desktop_file(d))
        d = "/usr/share/app-install/desktop/software-center:ubuntu-software-center.desktop"
        self.assertFalse(is_no_display_desktop_file(d))

    def test_split_icon_ext(self):
        from softwarecenter.utils import split_icon_ext
        for unchanged in ["foo.bar.baz", "foo.bar", "foo", 
                          "foo.pngx", "foo.png.xxx"]:
            self.assertEqual(split_icon_ext(unchanged), unchanged)
        for changed in ["foo.png", "foo.tiff", "foo.jpg", "foo.jpeg"]:
            self.assertEqual(split_icon_ext(changed), 
                            os.path.splitext(changed)[0])

    def test_get_nice_date_string(self):
        from softwarecenter.utils import get_nice_date_string

        now = datetime.datetime.utcnow()

        ten_secs_ago = now + datetime.timedelta(seconds=-10)
        self.assertEqual(get_nice_date_string(ten_secs_ago), 'a few minutes ago')

        two_mins_ago = now + datetime.timedelta(minutes=-2)
        self.assertEqual(get_nice_date_string(two_mins_ago), '2 minutes ago')

        under_a_day = now + datetime.timedelta(hours=-23, minutes=-59, seconds=-59)
        self.assertEqual(get_nice_date_string(under_a_day), '23 hours ago')

        under_a_week = now + datetime.timedelta(days=-4, hours=-23, minutes=-59, seconds=-59)
        self.assertEqual(get_nice_date_string(under_a_week), '4 days ago')

        over_a_week = now + datetime.timedelta(days=-7)
        self.assertEqual(get_nice_date_string(over_a_week), over_a_week.isoformat().split('T')[0])


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
