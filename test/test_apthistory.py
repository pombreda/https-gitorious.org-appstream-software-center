#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt
import apt_pkg
import datetime
import logging
import os
import unittest

from softwarecenter.apt.apthistory import AptHistory
from softwarecenter.utils import ExecutionTime

class testAptHistory(unittest.TestCase):

    def setUp(self):
        apt_pkg.Config.set("Dir::Log", "./data/apt-history")
        #apt_pkg.Config.set("Dir::Log::History", "./)

    def test_history(self):
        import datetime
        history = AptHistory()
        self.assertEqual(history.transactions[0].start_date,
                         datetime.datetime.strptime("2010-06-09 14:50:00",
                                                    "%Y-%m-%d  %H:%M:%S"))
        # 185 is from "zgrep Start data/apt-history/history.log*|wc -l"
        self.assertEqual(len(history.transactions), 185)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
