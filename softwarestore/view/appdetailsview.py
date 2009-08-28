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
import dbus
import logging
import gettext
import gtk
import gobject
import apt
import os
import pango
import subprocess
import sys
import time
import xapian

from urltextview import UrlTextView

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
 
from gettext import gettext as _

import dialogs

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

class AppDetailsView(UrlTextView):

    # the size of the icon on the left side
    APP_ICON_SIZE = 32
    APP_ICON_PADDING = 8

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends", "Recommends")
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,
                                 gobject.TYPE_PYOBJECT))
                    }

    def __init__(self, xapiandb, icons, cache):
        super(AppDetailsView, self).__init__()
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
        # customization
        self.set_editable(False)
        self.set_cursor_visible(False)
        self.set_wrap_mode(gtk.WRAP_WORD)
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # tags
        self._create_tag_table()
        # aptdaemon
        self.aptd_client = client.AptClient()
        self.window_main_xid = None
        # data
        self.appname = None

    def _create_tag_table(self):
        buffer = self.get_buffer()
        buffer.create_tag("align-to-icon", 
                          left_margin=self.APP_ICON_SIZE)
        buffer.create_tag("heading", 
                          weight=pango.WEIGHT_HEAVY,
                          scale=pango.SCALE_LARGE)
        #buffer.create_tag("align-right", 
        #                  justification=gtk.JUSTIFY_RIGHT))
        buffer.create_tag("small", 
                          scale=pango.SCALE_SMALL)
        buffer.create_tag("maint-status", 
                          scale_set=True,
                          scale=pango.SCALE_SMALL,
                          foreground="#888")

    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app '%s'" % appname)
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

        # data
        self.installed_rdeps = set()
            
        # fill the buffer
        self.clean()
        self.add_main_icon(self.iconname)
        self.add_main_description(appname, pkg)
        self.add_empty_lines(2)
        self.add_price(appname, pkg)
        self.add_enable_channel_button(doc, pkg)
        self.add_pkg_action_button_description(appname, pkg)
        self.add_pkg_action_button(appname, pkg, self.iconname)
        self.add_homepage_button(pkg)
        self.add_pkg_information(pkg)
        self.add_maintainance_end_dates(pkg)
        self.add_empty_lines(2)
        # emit select signal
        self.emit("selected", appname, pkg)

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
                pixbuf = self.icons.load_icon(MISSING_APP_ICON, 
                                              self.APP_ICON_SIZE, 0)
        else:
            pixbuf = self.icons.load_icon(MISSING_APP_ICON,
                                          self.APP_ICON_SIZE, 0)
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
        if not pkg or not pkg.candidate:
            return
        version = pkg.candidate.version
        if version:
            buffer.insert(iter, "\n\n")
            s = _("Version: %s (%s)") % (version, pkg.name)
            buffer.insert_with_tags_by_name(iter, s, "align-to-icon", "small")

    def add_main_description(self, appname, pkg):
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        if pkg and pkg.candidate:
            details = pkg.candidate.description
        else:
            details = _("Not available in the current data")

        heading = "%s" % appname
        text = "\n\n%s" % details
        buffer.insert_with_tags_by_name(iter, heading, "heading")
        buffer.insert_with_tags_by_name(iter, text, "align-to-icon")
        

    def add_enable_channel_button(self, doc, pkg):
        """add enable-channel button (if needed)"""
        # we have the pkg already
        if pkg and pkg.candidate and pkg.candidate.downloadable:
            return
        channel = doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
        if not channel:
            return
        path = APP_INSTALL_CHANNELS_PATH+channel+".list"
        if not os.path.exists(path):
            return
        # FIXME: deal with the EULA stuff
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        button = self._insert_button(iter, ["align-to-icon"])
        button.set_label(_("Enable channel"))
        button.connect("clicked", self.on_enable_channel_clicked, path)

    def on_enable_channel_clicked(self, widget, channelfile):
        #print "on_enable_channel_clicked"
        # FIXME: move this to utilities or something
        import aptsources.sourceslist

        # read channel file and add all relevant lines
        for line in open(channelfile):
            line = line.strip()
            if not line:
                continue
            entry = aptsources.sourceslist.SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(channelfile)
            try:
                self.aptd_client.add_repository(
                    entry.type, entry.uri, entry.dist, entry.comps, 
                    "Added by software-store", sourcepart)
            except dbus.exceptions.DBusException, e:
                if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                    return
        # now set the button to insensitive and wait
        widget.set_sensitive(False)
        trans = self.aptd_client.update_cache(
            exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def add_maintainance_end_dates(self, pkg):
        """add the end of the maintainance time"""
        # FIXME: add code
        return

    def add_pkg_action_button_description(self, appname, pkg):
        """Add message specific to this package (e.g. how many dependenies"""
        if not pkg:
            return 
        buffer = self.get_buffer()
        iter = buffer.get_end_iter()
        # its installed, tell about rdepends
        if pkg.installed:
            # generic message
            s = _("%s is installed on this computer.") % appname
            # show how many packages on the system depend on this
            self.installed_rdeps = set()
            for rdep in pkg._pkg.RevDependsList:
                if rdep.DepType in self.DEPENDENCY_TYPES:
                    rdep_name = rdep.ParentPkg.Name
                    if (self.cache.has_key(rdep_name) and
                        self.cache[rdep_name].isInstalled):
                        self.installed_rdeps.add(rdep.ParentPkg.Name)
            if len(self.installed_rdeps) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is used by %s piece of installed software.",
                    "It is used by %s pieces of installed software.",
                    len(self.installed_rdeps)) % len(self.installed_rdeps)
            buffer.insert_with_tags_by_name(iter,s, "align-to-icon")
            buffer.insert(iter, "\n\n")

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
        if not pkg.candidate:
            return
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
    def on_button_homepage_clicked(self, button, url):
        logging.debug("on_button_homepage_clicked: '%s'" % url)
        cmd = self._url_launch_app()
        subprocess.call([cmd, url])

    def _run_transaction(self, trans):
        trans.set_data("appname", self.appname)
        trans.set_data("iconname", self.iconname)
        trans.set_data("pkgname", self.pkgname)
        try:
            trans.run()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                pass
            else:
                raise

    def on_button_upgrade_clicked(self, button):
        #print "on_button_upgrade_clicked", pkgname
        trans = self.aptd_client.commit_packages([], [], [], [], [self.pkgname], 
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def remove(self):
        # generic removal text
        primary=_("%s depends on other software on the system. ") % self.appname
        secondary = _("Uninstalling it means that the following "
                      "additional software needs to be removed.")
        # alter it if a meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in self.installed_rdeps:
                primary=_("%s is a core component") % self.appname
                secondary = _("%s is a core application in Ubuntu. "
                              "Uninstalling it may cause future upgrades "
                              "to be incomplete. Are you sure you want to "
                              "continue?") % self.appname
                break
        # ask for confirmation if we have rdepends
        if len(self.installed_rdeps):
            if not dialogs.confirm_remove(None, primary, secondary, 
                                          self.cache,
                                          list(self.installed_rdeps)):
                return
        # do it (no rdepends or user confirmed)
        trans = self.aptd_client.commit_packages([], [], [self.pkgname], [], [],
                                         exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_remove_clicked(self, button):
        self.remove()

    def install(self):
        trans = self.aptd_client.commit_packages([self.pkgname], [], [], [], [],
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_install_clicked(self, button):
        #print "on_button_install_clicked", pkgname
        self.install()

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
        self.cache.open()
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

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    
    cache = apt.Cache()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsView(db, icons, cache)
    #view.show_app("AMOR")
    #view.show_app("3D Chess")
    view.show_app("Configuration Editor")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
