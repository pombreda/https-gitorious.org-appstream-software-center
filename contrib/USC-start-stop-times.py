#!/usr/bin/env python

import ldtp
import time
import unittest

start_time = time.time()


class TestCaseUSCStartStop(unittest.TestCase):

    def setUp(self):
        ldtp.launchapp('software-center')
        assert ldtp.waittillguiexist('frmUbuntuSoftwareCent*')
        print sorted(ldtp.getapplist())
        print ldtp.getmemorystat('xchat')
        self.msgs = []
        a = "Time taken for the frame to open is " + str(
            time.time() - start_time)
        self.msgs.append(a)

    def tearDown(self):
        ldtp.selectmenuitem('frmUbuntuSoftwareCenter', 'mnuClose')
        assert ldtp.waittillguinotexist('frmUbuntuSoftwareCent*')
        c = "This test took a total of " + str(time.time() - start_time)
        self.msgs.append(c)
        print '\n'.join(self.msgs)

    def test_1(self):
        ldtp.waittillguiexist('frmUbuntuSoftwareCent*', 'btnAccessories')
        assert ldtp.objectexist('frmUbuntuSoftwareCent*', 'btnAccessories')
        b = "Time taken from start to find the Accessories button " + str(
            time.time() - start_time)
        self.msgs.append(b)


if __name__ == "__main__":
    unittest.main()
