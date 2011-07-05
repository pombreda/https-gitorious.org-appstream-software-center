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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf


import logging
import tempfile
import time

#from softwarecenter.enums import *
from softwarecenter.utils import SimpleFileDownloader
from spinner import SpinnerView

ICON_EXCEPTIONS = ["gnome"]

class Url404Error(IOError):
    pass

class Url403Error(IOError):
    pass

class ShowImageDialog(Gtk.Dialog):
    """A dialog that shows a image """

    def __init__(self, title, url, missing_img, path=None, parent=None):
        Gtk.Dialog.__init__(self)

        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = parent.get_parent()
        # missing
        self._missing_img = missing_img
        self.image_filename = self._missing_img
        
        # create a spinner view to display while the screenshot it loading
        self.spinner_view = SpinnerView()

        # screenshot
        self.img = Gtk.Image()

        # downloader
        self.loader = SimpleFileDownloader()
        self.loader.connect('file-download-complete', self._on_screenshot_download_complete)
        self.loader.connect('file-url-reachable', self._on_screenshot_query_complete)

        # scolled window for screenshot
        viewport = Gtk.Viewport()
        viewport.add(self.img)
        viewport.set_shadow_type(Gtk.ShadowType.NONE)
        viewport.show()
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(viewport)
        
        # dialog
        self.set_transient_for(parent)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.get_content_area().add(self.spinner_view)
        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
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
        self._finished = False
        self._abort = False
        self._fetched = 0.0
        self._percent = 0.0
        self.loader.download_file(self.url, self.path)
        # wait for download to finish or for abort
        while not self._finished:
            time.sleep(0.1)
            while Gtk.events_pending():
                Gtk.main_iteration()
        # aborted
        if self._abort:
            return Gtk.ResponseType.CLOSE
        # load into icon
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.image_filename)
        except:
            logging.debug("The image format couldn't be determined")
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(self._missing_img)
            
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
        Gtk.Dialog.run(self)

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


class SimpleShowImageDialog(Gtk.Dialog):
    """A dialog that shows a image """

    DEFAULT_WIDTH = 850
    DEFAULT_HEIGHT = 650

    def __init__(self, title, pixbuf, parent=None):
        Gtk.Dialog.__init__(self)
        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = parent.get_parent()

        # screenshot
        img = Gtk.Image.new_from_pixbuf(pixbuf)

        # scolled window for screenshot
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC,
                               Gtk.PolicyType.AUTOMATIC)
        scroll.add_with_viewport(img)
        content_area = self.get_content_area()
        content_area.pack_start(scroll, True, True, 0)

        # dialog
        self.set_title(title)
        self.set_transient_for(parent)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.add_button(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.set_default_size(SimpleShowImageDialog.DEFAULT_WIDTH,
                              SimpleShowImageDialog.DEFAULT_HEIGHT)
        
    def run(self):
        # show all and run the real thing
        self.show_all()
        Gtk.Dialog.run(self)


if __name__ == "__main__":
    # invalid url
    d = ShowImageDialog("Synaptic Screenshot", "http://not-htere", "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()

    # valid url
    url = "http://screenshots.ubuntu.com/screenshot/synaptic"
    d = ShowImageDialog("Synaptic Screenshot", url, "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()
