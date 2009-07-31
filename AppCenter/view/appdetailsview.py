#!/usr/bin/python

import apt
import logging
import gtk
import gobject
import apt
import os
import xapian
import time

from gettext import gettext as _

XAPIAN_VALUE_PKGNAME = 171
XAPIAN_VALUE_ICON = 172
XAPIAN_VALUE_GETTEXT_DOMAIN = 173

class AppDetailsView(gtk.TextView):
    def __init__(self, xapiandb, icons, cache):
        gtk.TextView.__init__(self)
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(gtk.WRAP_WORD)
    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app %s" % appname)
        # get xapian document
        doc = None
        for m in self.xapiandb.postlist("AA"+appname):
            print m
            doc = self.xapiandb.get_document(m.docid)
            break
        if not doc:
            raise IndexError, "No app '%s' in database" % appname
        # icon
        iconname = doc.get_value(XAPIAN_VALUE_ICON)
        # get apt cache data
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        if self.cache.has_key(pkgname):
            details = self.cache[pkgname].description
        else:
            details = _("Not available in apt cache")
        # set buffer
        buffer = self.get_buffer()
        text = "%s\n\n%s" % (appname, details)
        buffer.set_text(text)
        if iconname:
            pixbuf = self.icons.load_icon(iconname, 32, 0)
            #self.image.set_from_pixbuf(pixbuf)
            iter = buffer.get_start_iter()
            buffer.insert_pixbuf(iter, pixbuf)

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
    view.show_app("AMOR")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
