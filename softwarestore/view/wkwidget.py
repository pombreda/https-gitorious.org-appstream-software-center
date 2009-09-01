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
import string

gobject.threads_init()
import webkit

class WebkitWidget(webkit.WebView):
    """Widget that uses a webkit html form for its drawing

    All i18n should be done *outside* the html, currently
    no i18n supported. So all user visible strings should
    be set via templates.

    It support calls to functions via javascript title change
    methods. The title should look like any of those:
    - "call:func_name"
    - "call:func_name:argument"
    - "call:func_name:arg1,args2"
    """
    def __init__(self, datadir, substitute=None):
        webkit.WebView.__init__(self)
        self.datadir = datadir
        self._template = ""
        self._html = ""
        self.connect('title-changed', self._on_title_changed)
        self._load()
        if not substitute:
            substitute = {}
        self._substitute(substitute)
        self._render()

    # internal helpers
    def _load(self):
        class_name = self.__class__.__name__        
        self._html_path = self.datadir+"/templates/%s.html" % class_name
        logging.debug("looking for '%s'" % self._html_path)
        if os.path.exists(self._html_path):
            self._template = open(self._html_path).read()

    def _render(self):
        # FIXME: use self._html_path here as base_uri ?
        self.load_html_string(self._html, "file:/") 

    def _substitute(self, subs):
        self._html = string.Template(self._template).safe_substitute(subs)

    # internal callbacks
    def _on_title_changed(self, view, frame, title):
        logging.debug("%s: title_changed %s %s %s" % (self.__class__.__name__,
                                                      view, frame, title))
        # no op - needed to reset the title after a action so that
        #         the action can be triggered again
        if title.startswith("nop"):
            return
        # call directive looks like:
        #  "call:func:arg1,arg2"
        #  "call:func"
        if title.startswith("call:"):
            args_str = ""
            args_list = []
            # try long form (with arguments) first
            try:
                (t,funcname,args_str) = title.split(":")
            except ValueError:
                # now try short (without arguments)
                (t,funcname) = title.split(":")
            if args_str:
                args_list = args_str.split(",")
            # see if we have it and if it can be called
            f = getattr(self, funcname)
            if f and callable(f):
                f(*args_list)
            # now we need to reset the title
            self.execute_script('document.title = "nop"')

class WKTestWidget(WebkitWidget):

    def func1(self, arg1, arg2):
        print "func1: ", arg1, arg2

    def func2(self):
        print "func2"

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-store"


    subs = {
        'key' : 'subs value' 
    }
    w = WKTestWidget(datadir, subs)

    win = gtk.Window()
    scroll = gtk.ScrolledWindow()
    scroll.add(w)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
