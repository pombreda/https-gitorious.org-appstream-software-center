# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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

import gconf
import glib
import gio
import gtk
import logging
import tempfile
import time
import threading
import gobject

from softwarecenter.enums import *
from softwarecenter.utils import ImageDownloader
from spinner import SpinnerView

ICON_EXCEPTIONS = ["gnome"]

class Url404Error(IOError):
    pass

class Url403Error(IOError):
    pass

class ShowImageDialog(gtk.Dialog):
    """A dialog that shows a image """

    def __init__(self, title, url, missing_img, path=None, parent=None):
        gtk.Dialog.__init__(self)
        self.set_has_separator(False)
        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = w.get_parent()
        # missing
        self._missing_img = missing_img
        self.image_filename = self._missing_img
        
        # create a spinner view to display while the screenshot it loading
        self.spinner_view = SpinnerView()

        # screenshot
        self.img = gtk.Image()

        # downloader
        self.loader = SimpleFileDownloader()
        self.loader.connect('image-download-complete', self._on_screenshot_download_complete)
        self.loader.connect('image-url-reachable', self._on_screenshot_query_complete)

        # scolled window for screenshot
        viewport = gtk.Viewport()
        viewport.add(self.img)
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.show()
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(viewport)
        
        # dialog
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.get_content_area().add(self.spinner_view)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.set_default_size(850,650)
        self.set_title(title)
        self.connect("response", self._response)
        # destination
        if not path:
            tempfile.mkdtemp(prefix="sc-screenshot")
        self.path = path
        # data
        self.url = url
            
    def _response(self, dialog, reponse_id):
        self._finished = True
        self._abort = True
        
    def run(self):
        self.spinner_view.start()
        self.show_all()
        # thread
        self._finished = False
        self._abort = False
        self._fetched = 0.0
        self._percent = 0.0
        self.loader.begin_download(self.url, self.path)
        # wait for download to finish or for abort
        while not self._finished:
            time.sleep(0.1)
            while gtk.events_pending():
                gtk.main_iteration()
        # aborted
        if self._abort:
            return gtk.RESPONSE_CLOSE
        # load into icon
        try:
            pixbuf = gtk.gdk.pixbuf_new_from_file(self.image_filename)
        except:
            logging.debug("The image format couldn't be determined")
            pixbuf = gtk.gdk.pixbuf_new_from_file(self._missing_img)
            
        # Set the screenshot image
        self.img.set_from_pixbuf(pixbuf)
        
        # Destroy the spinner view
        self.spinner_view.stop()
        self.spinner_view.destroy()
        
        # Add our screenshot image and scrolled window
        self.get_content_area().add(self.scroll)
        # and show them
        self.img.show()
        self.scroll.show() 

        # and run the real thing
        gtk.Dialog.run(self)

    def _on_screenshot_query_complete(self, loader, reachable):
        # show generic image if missing
        if not reachable:
            self.image_filename = self._missing_img
            self._finished = True

    def _on_screenshot_download_complete(self, loader, screenshot_path):
        self.image_filename = screenshot_path
        self._finished = True

    def _progress(self, count, block, total):
        "fetcher progress reporting"
        logging.debug("_progress %s %s %s" % (count, block, total))
        #time.sleep(1)
        self._fetched += block
        # ensure we do not go over 100%
        self._percent = min(self._fetched/total, 1.0)

if __name__ == "__main__":
    # invalid url
    d = ShowImageDialog("Synaptic Screenshot", "http://not-htere", "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()

    # valid url
    url = "http://screenshots.ubuntu.com/screenshot/synaptic"
    d = ShowImageDialog("Synaptic Screenshot", url, "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()
