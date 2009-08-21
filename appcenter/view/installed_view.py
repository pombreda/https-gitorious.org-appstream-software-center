#!/usr/bin/python

import logging
import gtk
import gobject
import apt
import os
import xapian
import time

from appview import *

class InstalledFilter(object):
    def __init__(self, cache):
        self.cache = cache
    def filter(self, pkgname):
        if self.cache.has_key(pkgname) and self.cache[pkgname].isInstalled:
            return True
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    cache = apt.Cache()
    installed_filter = InstalledFilter(cache)

    # now the store
    store = AppStore(db, icons, filter=installed_filter.filter)
    print len(store)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (db, view))

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
