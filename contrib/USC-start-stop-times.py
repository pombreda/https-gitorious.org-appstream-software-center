#!/usr/bin/env python

import ldtp
import locale
import os
import sys
import time
import unittest

start_time = time.time()

class ss_of_USC(unittest.TestCase):
    def setUp(self):
        ldtp.launchapp('software-center')
        assert ldtp.waittillguiexist('frmUbuntuSoftwareCenter')
        print sorted(ldtp.getapplist())
        print ldtp.getmemorystat('xchat')
        self.msgs = []
        a = "Time taken for the frame to open is " + str(time.time() - start_time)
        self.msgs.append(a)

    def tearDown(self):
        ldtp.selectmenuitem('frmUbuntuSoftwareCenter', 'mnuClose')
        assert ldtp.waittillguinotexist('frmUbuntuSoftwareCenter')
        c = "This test took a total of " + str(time.time() - start_time)
        self.msgs.append(c)
        print '\n'.join(self.msgs)

    def test_1(self):
        ldtp.waittillguiexist('frmUbuntuSoftwareCenter', 'btnAccessories')
        assert ldtp.objectexist('frmUbuntuSoftwareCenter', 'btnAccessories')
        b = "Time taken from start to find the Accessories button " + str(time.time() - start_time)
        self.msgs.append(b)


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "C")
    unittest.main()
