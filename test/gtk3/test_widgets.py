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

class TestWidgets(unittest.TestCase):
    """ basic tests for the various gtk3 widget """

    def test_stars(self):
        from softwarecenter.ui.gtk3.widgets.stars import get_test_stars_window
        win = get_test_stars_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_actionbar(self):
        from softwarecenter.ui.gtk3.widgets.actionbar import ActionBar
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
        from softwarecenter.ui.gtk3.widgets.backforward import get_test_backforward_window
        win = get_test_backforward_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_containers(self):
        from softwarecenter.ui.gtk3.widgets.containers import get_test_container_window
        win = get_test_container_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_description(self):
        from softwarecenter.ui.gtk3.widgets.description import get_test_description_window
        win = get_test_description_window()
        win.show_all()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_exhibits(self):
        from softwarecenter.ui.gtk3.widgets.exhibits import get_test_exhibits_window
        win = get_test_exhibits_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_show_image_dialog(self):
        from softwarecenter.ui.gtk3.widgets.imagedialog import SimpleShowImageDialog
        if os.path.exists("../../data/images/arrows.png"):
            f = "../../data/images/arrows.png"
        else:
            f = "../data/images/arrows.png"
        pix = GdkPixbuf.Pixbuf.new_from_file(f)
        d = SimpleShowImageDialog("test caption", pix)
        GObject.timeout_add(TIMEOUT, lambda: d.destroy())
        d.run()

    def test_reviews(self):
        from softwarecenter.ui.gtk3.widgets.reviews import get_test_reviews_window
        win = get_test_reviews_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_searchentry(self):
        from softwarecenter.ui.gtk3.widgets.searchentry import get_test_searchentry_window
        win = get_test_searchentry_window()
        s = "foo"
        win.entry.insert_text(s, len(s))
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_spinner(self):
        from softwarecenter.ui.gtk3.widgets.spinner import get_test_spinner_window
        win = get_test_spinner_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_symbolic_icons(self):
        from softwarecenter.ui.gtk3.widgets.symbolic_icons import get_test_symbolic_icons_window
        win = get_test_symbolic_icons_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_buttons(self):
        from softwarecenter.ui.gtk3.widgets.buttons import get_test_buttons_window
        win = get_test_buttons_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_screenshot_thumbnail(self):
        from softwarecenter.ui.gtk3.widgets.thumbnail import get_test_screenshot_thumbnail_window
        win = get_test_screenshot_thumbnail_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

    def test_videoplayer(self):
        from softwarecenter.ui.gtk3.widgets.videoplayer import get_test_videoplayer_window
        win = get_test_videoplayer_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()


    def test_apptreeview(self):
        from softwarecenter.ui.gtk3.widgets.apptreeview import get_test_window
        win = get_test_window()
        GObject.timeout_add(TIMEOUT, lambda: win.destroy())
        Gtk.main()

        

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
