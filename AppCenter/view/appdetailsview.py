#!/usr/bin/python

import apt
import logging
import gtk
import gobject
import apt
import os
import xapian
import time

class AppDetailsView(gtk.TextView):
    def __init__(self, xapiandb, icons, cache):
        gtk.TextView.__init__(self)
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app %s" % appname)
        buffer = self.get_buffer()
        buffer.set_text(appname)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    cache = apt.Cache()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsView(db, icons, cache)
    view.show_app("3dchess")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
