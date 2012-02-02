#!/usr/bin/python

import os
import unittest


from testutils import setup_test_env
setup_test_env()
from softwarecenter.i18n import (
    init_locale, 
    get_language,  get_languages, langcode_to_name,
    get_region)

class TestI18n(unittest.TestCase):
    """ tests the sc i18n """

    def test_langcode_to_name(self):
        self.assertEqual(langcode_to_name("de"), "German")

    def test_locale(self):
        # needs lang + country code
        os.environ["LANGUAGE"] = "zh_TW"
        self.assertEqual(get_language(), "zh_TW")
        # language only
        os.environ["LANGUAGE"] = "fr_FR"
        self.assertEqual(get_language(), "fr")
        # not existing one
        os.environ["LANGUAGE"] = "xx_XX"
        self.assertEqual(get_language(), "en")
        # LC_ALL, no language
        del os.environ["LANGUAGE"]
        os.environ["LC_ALL"] = "C"
        os.environ["LANG"] = "C"
        self.assertEqual(get_language(), "en")

    def test_invalid_get_languages(self):
        # set LANGUAGE to a invalid language and verify that it correctly
        # falls back to english
        os.environ["LANGUAGE"] = "yxy_YYY"
        self.assertEqual(get_languages(), ["en"])

    def test_init_locale(self):
        import locale
        os.environ["LANGUAGE"] = ""
        os.environ["LC_ALL"] = "en_US.UTF-8"
        init_locale()
        self.assertEqual(
            locale.getlocale(locale.LC_MESSAGES), ("en_US", "UTF-8"))
        
    def test_get_region(self):
        os.environ["LC_ALL"] = "de_DE"
        self.assertEqual(get_region(), "DE")



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
