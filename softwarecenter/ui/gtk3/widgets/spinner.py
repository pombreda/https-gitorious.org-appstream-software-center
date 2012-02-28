# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gi
gi.require_version("Gtk", "3.0")
import os

from gi.repository import Gtk, GObject

from softwarecenter.paths import IMAGE_LOADING_INSTALLED

class Spinner(object):
    """
    A factory to create the appropriate spinner based on whether
    Gtk.Spinner is available (see LP: #637422, LP: #624204)
    """
    def __new__(cls, *args, **kwargs):
        try:
            spinner = Gtk.Spinner()
        except AttributeError:
            spinner = GifSpinner()
        return spinner

class GifSpinner(Gtk.VBox):
    """
    an alternative spinner implementation that uses an animated gif
    """
    def __init__(self):
        GObject.GObject.__init__(self)
        self.image = Gtk.Image()
        self.image.set_from_file(IMAGE_LOADING_INSTALLED)
        self.add(self.image)
        
    def start(self):
        pass
    def stop(self):
        pass
        
class SpinnerView(Gtk.Viewport):
    """
    a panel that contains a spinner preset to a standard size and centered
    an optional label_text value can be specified for display with the spinner
    """
    def __init__(self, label_text=""):
        Gtk.Viewport.__init__(self)
        self.spinner = Spinner()
        self.spinner.set_size_request(48, 48)
        
        # use a table for the spinner (otherwise the spinner is massive!)
        spinner_table = Gtk.Table(3, 3, False)
        self.spinner_label = Gtk.Label()
        self.spinner_label.set_markup('<big>%s</big>' % label_text)
        spinner_vbox = Gtk.VBox()
        spinner_vbox.pack_start(self.spinner, True, True, 0)
        spinner_vbox.pack_start(self.spinner_label, True, True, 10)
        spinner_table.attach(spinner_vbox, 1, 2, 1, 2, Gtk.AttachOptions.EXPAND, Gtk.AttachOptions.EXPAND)
        
        #~ self.modify_bg(Gtk.StateType.NORMAL, Gdk.Color(1.0, 1.0, 1.0))
        self.add(spinner_table)
        self.set_shadow_type(Gtk.ShadowType.NONE)
        
    def start(self):
        """
        start the spinner and show it
        """
        self.spinner.start()
        self.spinner.show()
        
    def stop(self):
        """
        stop the spinner and hide it
        """
        self.spinner.stop()
        self.spinner.hide()
        
    def set_text(self, spinner_text = ""):
        """
        useful for adding/removing/changing the label text after the spinner instance has been created
        """
        self.spinner_label.set_markup('<big>%s</big>' % spinner_text)

class SpinnerNotebook(Gtk.Notebook):

    (CONTENT_PAGE, 
     SPINNER_PAGE) = range(2)

    def __init__(self, content, msg=""):
        Gtk.Notebook.__init__(self)
        self.spinner_view = SpinnerView(msg)
        # its critical to show() the spinner early as otherwise
        # gtk_notebook_set_active_page() will not switch to it
        self.spinner_view.show() 
        if not "SOFTWARE_CENTER_DEBUG_TABS" in os.environ:
            self.set_show_tabs(False)
        self.set_show_border(False)
        self.append_page(content, Gtk.Label("content"))
        self.append_page(self.spinner_view, Gtk.Label("spinner"))

    def _unmask_installed_view_spinner(self):
        self.spinner_view.start()
        return False

    def show_spinner(self, msg=""):
        if msg:
            self.spinner_view.set_text(msg)
        # "mask" the spinner view momentarily to prevent it from flashing into
        # view in the case of short delays where it isn't actually needed
        GObject.timeout_add(100, self._unmask_installed_view_spinner)
        self.set_current_page(self.SPINNER_PAGE)
        self.spinner_view.start()

    def hide_spinner(self):
        self.spinner_view.stop()
        self.set_current_page(self.CONTENT_PAGE)

def get_test_spinner_window():        
    spinner_view = SpinnerView()
    spinner_view.start()
    
    window = Gtk.Window()
    window.add(spinner_view)
    window.set_size_request(600, 500)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.show_all()    
    window.connect('destroy', Gtk.main_quit)
    spinner_view.set_text("Loading...")
    return window

if __name__ == "__main__":
    win = get_test_spinner_window()
    Gtk.main()
