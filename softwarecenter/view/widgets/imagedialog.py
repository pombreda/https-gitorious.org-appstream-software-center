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
import gtk
import logging
import tempfile
import time
import threading
import urllib

from softwarecenter.enums import *
from softwarecenter.utils import get_http_proxy_string_from_gconf

class Url404Error(IOError):
    pass

class Url403Error(IOError):
    pass

class GnomeProxyURLopener(urllib.FancyURLopener):
    """A urllib.URLOpener that honors the gnome proxy settings"""
    def __init__(self, user_agent=USER_AGENT):
        proxies = {}
        http_proxy = get_http_proxy_string_from_gconf()
        if http_proxy:
            proxies = { "http" : http_proxy }
        urllib.FancyURLopener.__init__(self, proxies)
        self.version = user_agent
    def http_error_404(self, url, fp, errcode, errmsg, headers):
        logging.debug("http_error_404: %s %s %s" % (url, errcode, errmsg))
        raise Url404Error, "404 %s" % url
    def http_error_403(self, url, fp, errcode, errmsg, headers):
        logging.debug("http_error_403: %s %s %s" % (url, errcode, errmsg))
        raise Url403Error, "403 %s" % url

class ShowImageDialog(gtk.Dialog):
    """A dialog that shows a image """

    def __init__(self, title, url, loading_img, missing_img, parent=None):
        gtk.Dialog.__init__(self)
        # find parent window for the dialog
        if not parent:
            parent = self.get_parent()
            while parent:
                parent = w.get_parent()
        # missing
        self._missing_img = missing_img
        self.image_filename = self._missing_img
        # image
        self.img = gtk.Image()
        self.img.set_from_file(loading_img)
        self.img.show()

        # view port
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add_with_viewport(self.img)
        scroll.show() 

        # progress
        self.progress = gtk.ProgressBar()
        self.progress.show()

        # box
        vbox = gtk.VBox()
        vbox.pack_start(scroll)
        vbox.pack_start(self.progress, expand=False)
        vbox.show()
        # dialog
        self.set_transient_for(parent)
        self.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        self.get_content_area().add(vbox)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.set_default_size(850,650)
        self.set_title(title)
        self.connect("response", self._response)
        # install urlopener
        urllib._urlopener = GnomeProxyURLopener()
        # data
        self.url = url

    def _response(self, dialog, reponse_id):
        self._finished = True
        self._abort = True
        
    def run(self):
        self.show()
        self.progress.show()
        self.progress.set_fraction(0.0)
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
            self.progress.set_fraction(self._percent)
            while gtk.events_pending():
                gtk.main_iteration()
        # aborted
        if self._abort:
            return gtk.RESPONSE_CLOSE
        # load into icon
        self.progress.hide()
        self.img.set_from_file(self.image_filename)
        # and run the real thing
        gtk.Dialog.run(self)

    def _fetch(self):
        "fetcher thread"
        logging.debug("_fetch: %s" % self.url)
        self.location = tempfile.NamedTemporaryFile()
        try:
            (screenshot, info) = urllib.urlretrieve(self.url, 
                                                    self.location.name, 
                                                    self._progress)
            self.image_filename = self.location.name
        except (Url403Error, Url404Error), e:
            self.image_filename = self._missing_img
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
    loading = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"
    d = ShowImageDialog("Synaptic Screenshot", url, loading, pkgname)
    d.run()
