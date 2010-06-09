#!/usr/bin/python

import sys
sys.path.insert(0,"../")

import apt
import apt_pkg
import datetime
import glib
import logging
import os
import subprocess
import time
import unittest

from softwarecenter.apt.apthistory import AptHistory
from softwarecenter.utils import ExecutionTime

class testAptHistory(unittest.TestCase):

    def setUp(self):
        rundir = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.basedir = os.path.join(rundir, "./data/apt-history")
        apt_pkg.Config.set("Dir::Log", self.basedir)
        #apt_pkg.Config.set("Dir::Log::History", "./)

    def test_history(self):
        history = AptHistory()
        self.assertEqual(history.transactions[0].start_date,
                         datetime.datetime.strptime("2010-06-09 14:50:00",
                                                    "%Y-%m-%d  %H:%M:%S"))
        # 185 is from "zgrep Start data/apt-history/history.log*|wc -l"
        self.assertEqual(len(history.transactions), 185)

    def _glib_timeout(self):
        self._timeouts.append(time.time())
        return True

    def test_apthistory_rescan_big(self):
        """ create big history file and ensure that on rescan the
            events are still processed
        """
        self._timeouts = []
        new_history = os.path.join(self.basedir,"history.log.2")
        try:
            os.remove(new_history+".gz")
        except OSError: 
            pass
        history = AptHistory()
        self.assertEqual(len(history.transactions), 185)
        s = open(os.path.join(self.basedir,"history.log")).read()
        f = open(new_history,"w")
        for i in range(100):
            f.write(s)
        f.close()
        subprocess.call(["gzip", new_history])
        timer_id = glib.timeout_add(100, self._glib_timeout)
        with ExecutionTime("rescan %s byte file" % os.path.getsize(new_history+".gz")):
            history.rescan()
        glib.source_remove(timer_id)
        # verify rescan
        self.assertTrue(len(history.transactions) > 185)
        # check the timeouts
        self.assertTrue(len(self._timeouts) > 0)
        for i in range(len(self._timeouts)-1):
            # check that we get a max timeout of 0.2s
            if abs(self._timeouts[i] - self._timeouts[i+1]) > 0.2:
                raise
        os.remove(new_history+".gz")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
