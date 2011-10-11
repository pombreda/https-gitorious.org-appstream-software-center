#!/usr/bin/python

from gi.repository import Gtk, GdkPixbuf, GObject
import os
import sys
import unittest

from mock import Mock

sys.path.insert(0,"..")

# ensure datadir is pointing to the right place
import softwarecenter.paths
softwarecenter.paths.datadir = os.path.join(
    os.path.dirname(__file__), "..", "..", 'data')

# window destory timeout
TIMEOUT=100

class TestDialogs(unittest.TestCase):
    """ basic tests for the various gtk3 dialogs """

    def test_dependency_dialogs(self):
        from softwarecenter.ui.gtk3.dialogs.dependency_dialogs import get_test_dialog
        dia = get_test_dialog()
        GObject.timeout_add(TIMEOUT, 
                            lambda: dia.response(Gtk.ResponseType.ACCEPT))
        dia.run()
        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
