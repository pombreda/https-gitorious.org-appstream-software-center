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
import urllib
import gobject

from softwarecenter.enums import *
from softwarecenter.utils import GnomeProxyURLopener
from spinner import GifSpinner

ICON_EXCEPTIONS = ["gnome"]

class Url404Error(IOError):
    pass

class Url403Error(IOError):
    pass

# FIXME: use the utils.py:ImageDownloader here instead of a thread
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
        
        # loading spinner
        try:
            self.spinner = gtk.Spinner()
        except AttributeError:
            # worarkound for archlinux: see LP: #624204, LP: #637422
            self.spinner = GifSpinner()
        self.spinner.set_size_request(48, 48)
        self.spinner.start()
        self.spinner.show()
        
        # table for spinner (otherwise the spinner is massive!)
        self.table = gtk.Table(3, 3, False)
        self.table.attach(self.spinner, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)
        self.table.show()

        # screenshot
        self.img = gtk.Image()

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
        self.get_content_area().add(self.table)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.set_default_size(850,650)
        self.set_title(title)
        self.connect("response", self._response)
        # install urlopener
        urllib._urlopener = GnomeProxyURLopener()
        # destination
        if not path:
            tmpfile.mkdtemp(prefix="sc-screenshot")
        self.path = path
        # data
        self.url = url
            
    def _response(self, dialog, reponse_id):
        self._finished = True
        self._abort = True
        
    def run(self):
        self.show()
        # thread
        self._finished = False
        self._abort = False
        self._fetched = 0.0
        self._percent = 0.0
        t = threading.Thread(target=self._fetch)
        t.start()
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
        
        # Destroy the spinner and it's table
        self.table.destroy()
        self.spinner.destroy()
        
        # Add our screenshot image and scrolled window
        self.get_content_area().add(self.scroll)
        # and show them
        self.img.show()
        self.scroll.show() 

        # and run the real thing
        gtk.Dialog.run(self)

    def _fetch(self):
        "fetcher thread"
        logging.debug("_fetch: %s" % self.url)
        if os.path.exists(self.path):
            self.image_filename = self.path
        else:
            self.location = open(self.path, 'w')
            try:
                (screenshot, info) = urllib.urlretrieve(self.url, 
                                                        self.location.name, 
                                                        self._progress)
                self.image_filename = self.location.name
            except (Url403Error, Url404Error), e:
                self.image_filename = self._missing_img
                self.location.close()
                os.remove(self.location.name)
            except Exception, e:
                logging.exception("urlopen error")
        self._finished = True

    def _progress(self, count, block, total):
        "fetcher progress reporting"
        logging.debug("_progress %s %s %s" % (count, block, total))
        #time.sleep(1)
        self._fetched += block
        # ensure we do not go over 100%
        self._percent = min(self._fetched/total, 1.0)

if __name__ == "__main__":
    pkgname = "synaptic"
    url = "http://screenshots.ubuntu.com/screenshot/synaptic"
    d = ShowImageDialog("Synaptic Screenshot", url, "/usr/share/software-center/images/dummy-screenshot-ubuntu.png")
    d.run()
