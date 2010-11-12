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
import logging
import tempfile
import time
import threading
import urllib
import gobject

from softwarecenter.enums import IMAGE_LOADING_INSTALLED

class GifSpinner(gtk.VBox):
    """
    an alternative spinner that uses an animated gif for use when
    gtk.Spinner is not available
    (see LP: #637422, LP: #624204)
    """
    def __init__(self):
        gtk.VBox.__init__(self)
        self.image = gtk.Image()
        self.image.set_from_file(IMAGE_LOADING_INSTALLED)
        self.image.set_size_request(160, 100)
        self.add(self.image)
        
    def start(self):
        pass
    def stop(self):
        pass

if __name__ == "__main__":
    pkgname = "synaptic"
    url = "http://screenshots.ubuntu.com/screenshot/synaptic"
    d = ShowImageDialog("Synaptic Screenshot", url, "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()
