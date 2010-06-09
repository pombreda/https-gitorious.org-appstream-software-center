#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt
import apt_pkg
import datetime
import logging
import os
import subprocess
import unittest

from softwarecenter.apt.apthistory import AptHistory
from softwarecenter.utils import ExecutionTime

class testAptHistory(unittest.TestCase):

    def setUp(self):
        apt_pkg.Config.set("Dir::Log", "./data/apt-history")
        #apt_pkg.Config.set("Dir::Log::History", "./)

    def test_history(self):
        history = AptHistory()
        self.assertEqual(history.transactions[0].start_date,
                         datetime.datetime.strptime("2010-06-09 14:50:00",
                                                    "%Y-%m-%d  %H:%M:%S"))
        # 185 is from "zgrep Start data/apt-history/history.log*|wc -l"
        self.assertEqual(len(history.transactions), 185)

    def test_apthistory_rescan_big(self):
        new_history = "./data/apt-history/history.log.2"
        try:
            os.remove(new_history+".gz")
        except: pass
        history = AptHistory()
        self.assertEqual(len(history.transactions), 185)
        s = open("./data/apt-history/history.log").read()
        f = open(new_history,"w")
        for i in range(100):
            f.write(s)
        f.close()
        subprocess.call(["gzip", new_history])
        with ExecutionTime("rescan %s byte file" % os.path.getsize(new_history+".gz")):
            history.rescan()
        self.assertTrue(len(history.transactions) > 185)
        #os.remove(new_history+".gz")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
