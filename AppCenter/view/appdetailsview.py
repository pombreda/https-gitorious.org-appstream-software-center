#!/usr/bin/python

import apt
import logging
import gtk
import gobject
import apt
import os
import xapian
import time
import pango
import subprocess

from gettext import gettext as _

XAPIAN_VALUE_PKGNAME = 171
XAPIAN_VALUE_ICON = 172
XAPIAN_VALUE_GETTEXT_DOMAIN = 173

class AppDetailsView(gtk.TextView):

    # the size of the icon on the left side
    APP_ICON_SIZE = 32
    APP_ICON_PADDING = 8

    def __init__(self, xapiandb, icons, cache):
        gtk.TextView.__init__(self)
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self._create_tag_table()

    def _create_tag_table(self):
        buffer = self.get_buffer()
        tag = buffer.create_tag("align-to-icon")
        tag.set_property("left-margin", self.APP_ICON_SIZE)
        tag = buffer.create_tag("heading")
        tag.set_property("weight", pango.WEIGHT_HEAVY)
        tag.set_property("scale", pango.SCALE_LARGE)

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
        # clear buffer
        buffer = self.get_buffer()
        buffer.delete(buffer.get_start_iter(),
                      buffer.get_end_iter())
        # text
        heading = "%s" % appname
        text = "\n\n%s" % details
        iter = buffer.get_start_iter()
        # icon
        if iconname:
            try:
                pixbuf = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
            except gobject.GError, e:
                pixbuf = self._empty_pixbuf()
        else:
            pixbuf = self._empty_pixbuf()
        # insert it
        buffer.insert_pixbuf(iter, pixbuf)
        buffer.insert_with_tags_by_name(iter, heading, "heading")
        buffer.insert_with_tags_by_name(iter, text, "align-to-icon")

        # button homepage
        if (self.cache.has_key(pkgname) and 
            self.cache[pkgname].candidate):
            url = self.cache[pkgname].candidate.homepage
            if url:
                buffer.insert(iter, "\n\n")
                button = self._insert_button(iter, ["align-to-icon"])
                button.set_tooltip_text(url)
                button.connect("clicked", self.on_button_homepage_clicked, url)
    
    def _insert_button(self, iter, tag_names=None):
        """
        insert a gtk.Button into at iter with a (optinal) list of tag names
        """
        buffer = self.get_buffer()
        anchor = buffer.create_child_anchor(iter)
        # align-to-icon needs (start,end) and we can not just copy
        # the iter before create_child_anchor (it invalidates it)
        start = iter.copy()
        start.backward_char()
        if tag_names:
            for tag in tag_names:
                buffer.apply_tag_by_name(tag, start, iter)
        button = gtk.Button(_("Homepage"))
        button.show()
        self.add_child_at_anchor(button, anchor)
        return button

    def on_button_homepage_clicked(self, button, url):
        logging.debug("on_button_homepage_clicked: '%s'" % url)
        cmd = self._url_launch_app()
        subprocess.call([cmd, url])

    def _url_launch_app(self):
        """return the most suitable program for opening a url"""
        if "GNOME_DESKTOP_SESSION_ID" in os.environ:
            return "gnome-open"
        return "xdg-open"

    def _empty_pixbuf(self):
        return gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
                              self.APP_ICON_SIZE, self.APP_ICON_SIZE)

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
    #view.show_app("3D Chess")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
