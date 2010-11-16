#!/usr/bin/python

import apt
import glib
import gtk
import logging
from mock import Mock
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, "..")

from softwarecenter.app import SoftwareCenterApp
from softwarecenter.enums import XAPIAN_BASE_PATH
from softwarecenter.view.appview import AppStore
from softwarecenter.view.availablepane import AvailablePane
from softwarecenter.db.application import Application
from softwarecenter.view.catview import get_category_by_name
from softwarecenter.backend import get_install_backend

# FIXME:
#  - need proper fixtures for history and lists
#  - needs stats about cold/warm disk cache


class SCTestGUI(unittest.TestCase):

    def setUp(self):
        pass

    def test_startup_time(self):
        self.revno_to_times_list = {}
        for i in range(2):
            time_to_visible = self.create_ui_and_return_time_to_visible()
            self.record_test_run_data(time_to_visible)
        print self.revno_to_times_list 

    def create_ui_and_return_time_to_visible(self):
        os.environ["PYTHONPATH"] = ".."
        now = time.time()
        # we get the time on stdout and detailed stats on stderr
        (stdoutput, profile) = subprocess.Popen(
            ["../software-center", "--measure-startup-time"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        # this is the time spend inside python
        time_inside_python = stdoutput.strip().split("\n")[-1]
        # this is the time with the python statup overhead
        time_with_launching_python = time.time() - now
        # for testing
        print "time inside_python: ", time_inside_python
        print "total with launching python: ", time_with_launching_python
        return time_with_launching_python

    def record_test_run_data(self, time_to_visible):
        # gather stats
        revno = subprocess.Popen(["bzr","revno"], stdout=subprocess.PIPE).communicate()[0].strip()
        times_list = self.revno_to_times_list.get(revno, [])
        times_list.append(time_to_visible)
        self.revno_to_times_list[revno] = times_list

    # helper stuff
    def _p(self):
        """ process gtk events """
        while gtk.events_pending():
            gtk.main_iteration()


if __name__ == "__main__":
    unittest.main()
