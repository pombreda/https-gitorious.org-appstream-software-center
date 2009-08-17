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
        #tag = buffer.create_tag("align-right")
        #tag.set_property("justification", gtk.JUSTIFY_RIGHT)

    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app %s" % appname)
        # get xapian document
        doc = None
        for m in self.xapiandb.postlist("AA"+appname):
            doc = self.xapiandb.get_document(m.docid)
            break
        if not doc:
            raise IndexError, "No app '%s' in database" % appname
        # icon
        iconname = doc.get_value(XAPIAN_VALUE_ICON)
        # get apt cache data
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        pkg = None
        if self.cache.has_key(pkgname):
            pkg = self.cache[pkgname]

        # fill the buffer
        self.clean()
        self.add_main_icon(iconname)
        self.add_main_description(appname, pkg)
        self.add_empty_lines(2)
        self.add_enable_channel_button(doc)
        self.add_pkg_action_button(pkg)
        self.add_homepage_button(pkg)
        self.add_maintainance_end_dates(pkg)

    # helper to fill the buffer with the pkg information
    def clean(self):
        """clean the buffer"""
        buffer = self.get_buffer()
        buffer.delete(buffer.get_start_iter(),
                      buffer.get_end_iter())

    def add_empty_lines(self, count=1):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        for i in range(count):
            buffer.insert(iter, "\n")

    def add_main_icon(self, iconname):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        if iconname:
            try:
                pixbuf = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
            except gobject.GError, e:
                pixbuf = self._empty_pixbuf()
        else:
            pixbuf = self._empty_pixbuf()
        # insert description 
        buffer.insert_pixbuf(iter, pixbuf)

    def add_main_description(self, appname, pkg):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        if pkg:
            details = pkg.candidate.description
        else:
            details = _("Not available in the current data")

        heading = "%s" % appname
        text = "\n\n%s" % details
        buffer.insert_with_tags_by_name(iter, heading, "heading")
        buffer.insert_with_tags_by_name(iter, text, "align-to-icon")
        

    def add_enable_channel_button(self, doc):
        """add enable-channel button (if needed)"""
        # FIXME: add code
        return

    def add_maintainance_end_dates(self, pkg):
        """add the end of the maintainance time"""
        # FIXME: add code
        return
    
    def add_pkg_action_button(self, pkg):
        """add pkg action button (install/remove/upgrade)"""
        if not pkg:
            return 
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        button = self._insert_button(iter, ["align-to-icon"])
        if pkg.installed and pkg.isUpgradable:
            button.set_label(_("Upgrade"))
            button.connect("clicked", self.on_button_upgrade_clicked, pkg.name)
        elif pkg.installed:
            button.set_label(_("Remove"))
            button.connect("clicked", self.on_button_remove_clicked, pkg.name)
        else:
            button.set_label(_("Install"))
            button.connect("clicked", self.on_button_install_clicked, pkg.name)
    
    def add_homepage_button(self, pkg):
        """add homepage button to the current buffer"""
        if not pkg:
            return
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        url = pkg.candidate.homepage
        if not url:
            return
        # FIXME: right-align
        buffer.insert(iter, 4*" ")
        #button = self._insert_button(iter, ["align-right"])
        button = self._insert_button(iter)
        button.set_label(_("Homepage"))
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
        button = gtk.Button("")
        button.show()
        self.add_child_at_anchor(button, anchor)
        return button

    # callbacks
    def on_button_upgrade_clicked(self, button, pkgname):
        print "on_button_upgrade_clicked", pkgname

    def on_button_remove_clicked(self, button, pkgname):
        print "on_button_remove_clicked", pkgname

    def on_button_install_clicked(self, button, pkgname):
        print "on_button_install_clicked", pkgname

    def on_button_homepage_clicked(self, button, url):
        logging.debug("on_button_homepage_clicked: '%s'" % url)
        cmd = self._url_launch_app()
        subprocess.call([cmd, url])

    # internal helpers
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
