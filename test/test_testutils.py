#!/usr/bin/python

import logging
import unittest

import dbus
import time
from gi.repository import GObject

import sys
sys.path.insert(0,"../")

from softwarecenter.testutils import start_dummy_backend, stop_dummy_backend
from softwarecenter.backend.aptd import get_dbus_bus


class TestTestUtils(unittest.TestCase):

    def setUp(self):
        start_dummy_backend()

    def tearDown(self):
        stop_dummy_backend()

    def test_start_stop_dummy_backend(self):
        bus = get_dbus_bus()
        system_bus = dbus.SystemBus()
        session_bus = dbus.SessionBus()
        self.assertNotEqual(bus, system_bus)
        self.assertNotEqual(bus, session_bus)
        # get names and ...
        names = bus.list_names()
        # ensure we have the  following:
        #  org.freedesktop.DBus, 
        #  org.freedesktop.PolicyKit1
        #  org.debian.apt
        # (and :1.0, :1.1, :1.2)
        self.assertEqual(len(names), 6)

    def test_fake_aptd(self):
        from softwarecenter.backend import get_install_backend
        backend = get_install_backend()
        backend.install("2vcard", "", "")
        self._p()
        
    def _p(self):
        context = GObject.main_context_default()
        for i in range(10):
            while context.pending():
                context.iteration()
            time.sleep(0.1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
