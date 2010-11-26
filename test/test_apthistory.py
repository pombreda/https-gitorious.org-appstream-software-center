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

    def _get_apt_history(self):
        history = AptHistory()
        main_loop = glib.main_context_default()
        while main_loop.pending():
           main_loop.iteration()
        return history

    def setUp(self):
        rundir = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.basedir = os.path.join(rundir, "./data/apt-history")
        apt_pkg.Config.set("Dir::Log", self.basedir)
        #apt_pkg.Config.set("Dir::Log::History", "./)

    def test_history(self):
        history = self._get_apt_history()
        self.assertEqual(history.transactions[0].start_date,
                         datetime.datetime.strptime("2010-06-09 14:50:00",
                                                    "%Y-%m-%d  %H:%M:%S"))
        # 186 is from "zgrep Start data/apt-history/history.log*|wc -l"
        #print "\n".join([str(x) for x in history.transactions])
        self.assertEqual(len(history.transactions), 186)


    def test_apthistory_upgrade(self):
        history = self._get_apt_history()
        self.assertEqual(history.transactions[1].upgrade,
                         ['acl (2.2.49-2, 2.2.49-3)'])

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
        history = self._get_apt_history()
        self.assertEqual(len(history.transactions), 186)
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
        self.assertTrue(len(history.transactions) > 186)
        # check the timeouts
        self.assertTrue(len(self._timeouts) > 0)
        for i in range(len(self._timeouts)-1):
            # check that we get a max timeout of 0.2s
            if abs(self._timeouts[i] - self._timeouts[i+1]) > 0.2:
                raise
        os.remove(new_history+".gz")

    def test_no_history_log(self):
        # set to dir with no existing history.log
        apt_pkg.Config.set("Dir::Log", "/")
        # this should not raise
        history = self._get_apt_history()
        self.assertEqual(history.transactions, [])
        apt_pkg.Config.set("Dir::Log", self.basedir)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
