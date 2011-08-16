#!/usr/bin/python

import logging
import unittest

import sys
sys.path.insert(0,"../")

from softwarecenter.testutils import start_dummy_backend, stop_dummy_backend
from softwarecenter.backend.aptd import get_dbus_bus

class TestTestUtils(unittest.TestCase):

    def test_start_stop_dummy_backend(self):
        import dbus
        start_dummy_backend()
        bus = get_dbus_bus()
        system_bus = dbus.SystemBus()
        session_bus = dbus.SessionBus()
        self.assertNotEqual(bus, system_bus)
        self.assertNotEqual(bus, session_bus)
        # get names and ...
        names = bus.list_names()
        # ensure there is *only* the default org.freedesktop.DBus on the bus
        # and our fake polkit
        self.assertEqual(len(names), 2)
        stop_dummy_backend()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
