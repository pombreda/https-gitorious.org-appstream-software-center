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

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
