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

import apt
import logging
import gtk
import gobject
import apt
import os
import pango
import string
import subprocess
import sys
import time
import xapian

import webkit

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
 
from gettext import gettext as _

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

class AppDetailsView(webkit.WebView):

    # the size of the icon on the left side
    APP_ICON_SIZE = 32
    APP_ICON_PADDING = 8

    doc = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
       "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
 <title></title>
</head>
<body>
 <script type="text/javascript">
  function changeTitle(title) { document.title = title; }
 </script>

 <img src="file:$iconpath" alt="Application Icon" width=$width height=$height>
 <h1>$appname</h1>
 <p>$description</p>

 <input type="button" name="button_$action_button_value" 
        value="$action_button_label"
      onclick='changeTitle("run:on_button_${action_button_value}_clicked")'
 />

 <input type="button" name="button_homepage" value="Homepage"
      onclick='changeTitle("run:on_button_homepage_clicked")'
 />

</body>
</html>
"""

    def __init__(self, xapiandb, icons, cache):
        super(AppDetailsView, self).__init__()
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
        # customize
        #settings = self.get_settings()
        #settings.set_property("auto-load-images", True)
        # signals
        self.connect('title-changed', self.on_title_changed)
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # aptdaemon
        self.aptd_client = client.AptClient()
        self.window_main_xid = None
        # data
        self.appname = None
    
    def on_title_changed(self, view, frame, title):
        print "title_changed", view, frame, title
        if title.startswith("run:"):
            funcname = title.split(":")[1]
            f = getattr(self, funcname)
            if f:
                f()

    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app %s" % appname)
        self.appname = appname
        # get xapian document
        doc = None
        for m in self.xapiandb.postlist("AA"+appname):
            doc = self.xapiandb.get_document(m.docid)
            break
        if not doc:
            raise IndexError, "No app '%s' in database" % appname
        # icon
        self.iconname = doc.get_value(XAPIAN_VALUE_ICON)
        # get apt cache data
        self.pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        pkg = None
        if self.cache.has_key(self.pkgname):
            pkg = self.cache[self.pkgname]

        # description
        if pkg:
            details = pkg.candidate.description
        else:
            details = _("Not available in the current data")
        description = details.replace("\n","<p>")

        # icon
        iconinfo = self.icons.lookup_icon(self.iconname, self.APP_ICON_SIZE, 0)
        if iconinfo:
            iconpath = iconinfo.get_filename()
        else:
            iconpath = ""

        if pkg:
            self.homepage_url = pkg.candidate.homepage

        # button data
        if pkg:
            if pkg.installed and pkg.isUpgradable:
                action_button_label = _("Upgrade")
                action_button_value = "upgrade"
            elif pkg.installed:
                action_button_label = _("Remove")
                action_button_value = "remove"
            else:
                action_button_label = _("Install")
                action_button_value = "install"

        subs = { 'appname' : self.appname,
                 'pkgname' : self.pkgname,
                 'iconname' : self.iconname,
                 'description' : description,
                 'iconpath' : iconpath,
                 'width' : self.APP_ICON_SIZE,
                 'height' : self.APP_ICON_SIZE,
                 'action_button_label' : action_button_label,
                 'action_button_value' : action_button_value,
               }

        html = string.Template(self.doc).safe_substitute(subs)
        self.load_html_string(html, "file:/")
        return

        # fill the buffer
        self.clean()
        self.add_main_icon(iconname)
        self.add_main_description(appname, pkg)
        self.add_empty_lines(2)
        self.add_price(appname, pkg)
        self.add_enable_channel_button(doc)
        self.add_pkg_action_button(appname, pkg, iconname)
        self.add_homepage_button(pkg)
        self.add_pkg_information(pkg)
        self.add_maintainance_end_dates(pkg)
        self.add_empty_lines(2)

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

    def add_price(self, appname, pkg):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        s = _("Price: %s") % _("Free")
        s += "\n\n"
        buffer.insert_with_tags_by_name(iter, s, "align-to-icon", "small")

    def add_pkg_information(self, pkg):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        version = pkg.candidate.version
        if version:
            buffer.insert(iter, "\n\n")
            s = _("Version: %s (%s)") % (version, pkg.name)
            buffer.insert_with_tags_by_name(iter, s, "align-to-icon", "small")

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
    
    def add_pkg_action_button(self, appname, pkg, iconname):
        """add pkg action button (install/remove/upgrade)"""
        if not pkg:
            return 
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        button = self._insert_button(iter, ["align-to-icon"])
        if pkg.installed and pkg.isUpgradable:
            button.set_label(_("Upgrade"))
            button.connect("clicked", self.on_button_upgrade_clicked)
        elif pkg.installed:
            button.set_label(_("Remove"))
            button.connect("clicked", self.on_button_remove_clicked)
        else:
            button.set_label(_("Install"))
            button.connect("clicked", self.on_button_install_clicked)
    
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
    def on_button_homepage_clicked(self):
        cmd = self._url_launch_app()
        subprocess.call([cmd, self.homepage_url])

    def on_button_upgrade_clicked(self):
        #print "on_button_upgrade_clicked", pkgname
        pkgname = self.pkgname
        trans = self.aptd_client.commit_packages([], [], [], [], [pkgname], 
                                          exit_handler=self._on_trans_finished)
        trans.set_data("appname", self.appname)
        trans.set_data("iconname", self.iconname)
        trans.set_data("pkgname", self.pkgname)
        trans.run()

    def on_button_remove_clicked(self):
        #print "on_button_remove_clicked", pkgname
        pkgname = self.pkgname
        trans = self.aptd_client.commit_packages([], [], [pkgname], [], [],
                                         exit_handler=self._on_trans_finished)
        trans.set_data("pkgname", self.pkgname)
        trans.set_data("appname", self.appname)
        trans.set_data("iconname", self.iconname)
        trans.run()

    def on_button_install_clicked(self):
        #print "on_button_install_clicked", pkgname
        pkgname = self.pkgname
        trans = self.aptd_client.commit_packages([pkgname], [], [], [], [],
                                          exit_handler=self._on_trans_finished)
        trans.set_data("pkgname", self.pkgname)
        trans.set_data("appname", self.appname)
        trans.set_data("iconname", self.iconname)
        trans.run()

    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        #print "finish: ", trans, enum
        # FIXME: do something useful here
        if enum == enums.EXIT_FAILED:
            excep = trans.get_error()
            msg = "%s: %s\n%s\n\n%s" % (
                   _("ERROR"),
                   enums.get_error_string_from_enum(excep.code),
                   enums.get_error_description_from_enum(excep.code),
                   excep.details)
            print msg
        # re-open cache and refresh app display
        # FIXME: threaded to keep the UI alive
        self.cache.open(apt.progress.OpProgress())
        self.show_app(self.appname)

    # internal helpers
    def _url_launch_app(self):
        """return the most suitable program for opening a url"""
        if "GNOME_DESKTOP_SESSION_ID" in os.environ:
            return "gnome-open"
        return "xdg-open"

    def _empty_pixbuf(self):
        pix = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
                             self.APP_ICON_SIZE, self.APP_ICON_SIZE)
        pix.fill(0)
        return pix

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    gobject.threads_init()

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
