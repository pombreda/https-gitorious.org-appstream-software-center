#!/usr/bin/python

import glib
from gi.repository import Gtk, GdkPixbuf, GObject
import mock
import os
import sys
import unittest

sys.path.insert(0,"../..")

from mock import Mock

from softwarecenter.ui.gtk3.widgets.stars import get_test_stars_window
from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
from softwarecenter.ui.gtk3.widgets.backforward import get_test_backforward_window
from softwarecenter.ui.gtk3.widgets.containers import get_test_container_window
from softwarecenter.ui.gtk3.widgets.description import get_test_description_window
from softwarecenter.ui.gtk3.widgets.imagedialog import SimpleShowImageDialog
from softwarecenter.ui.gtk3.widgets.pathbar import get_test_pathbar_window, PathPart
from softwarecenter.ui.gtk3.widgets.reviews import get_test_reviews_window
from softwarecenter.ui.gtk3.widgets.searchentry import get_test_searchentry_window

# window destory timeout
TIMEOUT=1000

class TestWidgets(unittest.TestCase):
    """ basic tests for the various gtk3 widget """

    def test_stars(self):
        win = get_test_stars_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_actionbar(self):
        mock = Mock()
        actionbar = ActionBar()
        actionbar.add_button("id1", "label", mock)
        actionbar.add_button("id2", "label", mock)
        actionbar.remove_button("id2")
        win = Gtk.Window()
        win.set_size_request(400, 400)
        win.add(actionbar)
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_backforward(self):
        win = get_test_backforward_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_containers(self):
        win = get_test_container_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_description(self):
        win = get_test_description_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_show_image_dialog(self):
        pix = GdkPixbuf.Pixbuf.new_from_file("../../data/images/dummy-screenshot-ubuntu.png")
        d = SimpleShowImageDialog("test caption", pix)
        GObject.timeout_add(TIMEOUT, lambda: d.destroy())
        d.run()

    def test_show_image_dialog(self):
        win = get_test_pathbar_window()
        win.pb.append(PathPart("foo1"))
        win.pb.append(PathPart("foo2"))
        win.pb.pop()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_reviews(self):
        win = get_test_reviews_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_searchentry(self):
        win = get_test_searchentry_window()
        s = "foo"
        win.entry.insert_text(s, len(s))
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
