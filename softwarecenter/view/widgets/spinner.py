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


import gtk

from softwarecenter.enums import IMAGE_LOADING_INSTALLED

class Spinner(object):
    """
    A factory to create the appropriate spinner based on whether
    gtk.Spinner is available (see LP: #637422, LP: #624204)
    """
    def __new__(cls, *args, **kwargs):
        try:
            spinner = gtk.Spinner()
        except AttributeError:
            spinner = GifSpinner()
        return spinner

class GifSpinner(gtk.VBox):
    """
    an alternative spinner implementation that uses an animated gif
    """
    def __init__(self):
        gtk.VBox.__init__(self)
        self.image = gtk.Image()
        self.image.set_from_file(IMAGE_LOADING_INSTALLED)
        self.add(self.image)
        
    def start(self):
        pass
    def stop(self):
        pass
        
class SpinnerView(gtk.Viewport):
    """
    a panel that contains a spinner preset to a standard size and centered
    """
    def __init__(self, label_text=None):
        gtk.Viewport.__init__(self)
        self.spinner = Spinner()
        self.spinner.set_size_request(48, 48)
        
        # use a table for the spinner (otherwise the spinner is massive!)
        spinner_table = gtk.Table(3, 3, False)
        if label_text:
            spinner_label = gtk.Label()
            spinner_label.set_markup('<big>%s</big>' % label_text)
            spinner_vbox = gtk.VBox()
            spinner_vbox.pack_start(self.spinner, expand=False)
            spinner_vbox.pack_start(spinner_label, expand=True, padding=10)
            spinner_table.attach(spinner_vbox, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)
        else:
            spinner_table.attach(self.spinner, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)
        
        self.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(1.0, 1.0, 1.0))
        self.add(spinner_table)
        self.set_shadow_type(gtk.SHADOW_NONE)
        
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

if __name__ == "__main__":
    spinner_view = SpinnerView(label_text="Connecting to payment service...")
    spinner_view.start()
    
    window = gtk.Window()
    window.add(spinner_view)
    window.set_size_request(600, 500)
    window.set_position(gtk.WIN_POS_CENTER)
    window.show_all()
    window.connect('destroy', gtk.main_quit)

    gtk.main()
