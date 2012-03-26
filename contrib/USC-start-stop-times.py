#!/usr/bin/env python

import os
import sys
import unittest
import ldtp
import time

start_time = time.time()

class ss_of_USC(unittest.TestCase):
    def setUp(self):
        ldtp.launchapp('software-center')
        assert ldtp.waittillguiexist('frmUbuntuSoftwareCentre')
        print sorted(ldtp.getapplist())
        print ldtp.getmemorystat('xchat')
        self.msgs = []
        a = "Time taken for the frame to open is " + str(time.time() - start_time)
        self.msgs.append(a)

    def tearDown(self):
        ldtp.selectmenuitem('frmUbuntuSoftwareCentre', 'mnuClose')
        assert ldtp.waittillguinotexist('frmUbuntuSoftwareCentre')
        c = "This test took a total of " + str(time.time() - start_time)
        self.msgs.append(c)
        print '\n'.join(self.msgs)

    def test_1(self):
        ldtp.waittillguiexist('frmUbuntuSoftwareCentre', 'btnAccessories')
        assert ldtp.objectexist('frmUbuntuSoftwareCentre', 'btnAccessories')
        b = "Time taken from start to find the Accessories button " + str(time.time() - start_time)
        self.msgs.append(b)


if __name__ == "__main__":
    unittest.main()
