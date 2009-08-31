# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


import gobject
import gtk
import logging
import os

gobject.threads_init()
import webkit

class WebkitWidget(webkit.WebView):
    
    def __init__(self, datadir):
        webkit.WebView.__init__(self)
        self.datadir = datadir
        self._html = ""
        self._load()
    def _load(self):
        class_name = self.__class__.__name__        
        self._html_path = datadir+"/templates/%s.html" % class_name
        if os.path.exists(self._html_path):
            self._html = open(self._html_path).read()
            self._render()
    def _render(self):
        # FIXME: use self._html_path here as base_uri ?
        self.load_html_string(self._html, "/") 

class WKTestWidget(WebkitWidget):
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-store"


    w = WKTestWidget(datadir)

    win = gtk.Window()
    scroll = gtk.ScrolledWindow()
    scroll.add(w)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
