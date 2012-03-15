#!/usr/bin/python

import unittest

from mock import patch

from testutils import setup_test_env
setup_test_env()
from softwarecenter.hw import (
    get_hardware_support_for_tags, OPENGL_DRIVER_BLACKLIST_TAG)

class TestHW(unittest.TestCase):
    """ tests the hardware support detection """

    def test_get_hardware_support_for_tags(self):
        tags = [OPENGL_DRIVER_BLACKLIST_TAG + "intel",
                "hardware::input:mouse",
               ]
        with patch("debtagshw.opengl.get_driver") as mock_get_driver:
            # test with the intel driver
            mock_get_driver.return_value = "intel"
            supported = get_hardware_support_for_tags(tags)
            self.assertEqual(supported[tags[0]], "no")
            self.assertEqual(len(supported), 2)
            # now with fake amd driver
            mock_get_driver.return_value = "amd"
            supported = get_hardware_support_for_tags(tags)
            self.assertEqual(supported[tags[0]], "yes")

if __name__ == "__main__":
    #import logging
    #logging.basicConfig(level=logging.DEBUG)
    unittest.main()
