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
import string
import subprocess
import sys
import time
import xapian

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
 
from gettext import gettext as _

from wkwidget import WebkitWidget
import dialogs

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

class AppDetailsView(WebkitWidget):

    # the size of the icon on the left side
    APP_ICON_SIZE = 48
    APP_ICON_PADDING = 8

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends", "Recommends")
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,
                                 gobject.TYPE_PYOBJECT))
                    }


    def __init__(self, xapiandb, icons, cache, datadir):
        super(AppDetailsView, self).__init__(datadir)
        self.xapiandb = xapiandb
        self.icons = icons
        self.cache = cache
        self.datadir = datadir
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # aptdaemon
        self.aptd_client = client.AptClient()
        self.window_main_xid = None
        # data
        self.appname = None
        # setup missing icon
        iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, 
                                          self.APP_ICON_SIZE, 0)
        self.MISSING_ICON_PATH = iconinfo.get_filename()
        
    
    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app '%s'" % appname)

        # app specific data
        self.appname = appname
        self.installed_rdeps = set()
        self.homepage_url = None
        self.installed = "hidden"
        self.channelfile = None

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
        description = details.replace("*","</p><p>*")
        description = description.replace("\n-","</p><p>-")
        description = description.replace("\n\n","</p><p>")

        # icon
        iconinfo = self.icons.lookup_icon(self.iconname, self.APP_ICON_SIZE, 0)
        if iconinfo:
            iconpath = iconinfo.get_filename()
        else:
            iconpath = self.MISSING_ICON_PATH

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
                self.installed = "visible"
            else:
                action_button_label = _("Install")
                action_button_value = "install"
                self.installed = "hidden"
        else:
            channel = doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            if channel:
                path = APP_INSTALL_CHANNELS_PATH + channel +".list"
                if os.path.exists(path):
                    self.channelfile = path
                    # FIXME: deal with the EULA stuff
                    action_button_label = _("Enable channel")
                    action_button_value = "enable_channel"

        # subs dict
        subs = { 'appname' : self.appname,
                 'pkgname' : self.pkgname,
                 'iconname' : self.iconname,
                 'description' : description,
                 'iconpath' : iconpath,
                 'width' : self.APP_ICON_SIZE,
                 'height' : self.APP_ICON_SIZE,
                 'action_button_label' : action_button_label,
                 'action_button_value' : action_button_value,
                 'homepage_button_visibility' : self.get_homepage_button_visibility(),
                 'datadir' : os.path.abspath(self.datadir),
                 'installed' : self.installed,
                 'price' : _("Price: %s") % _("Free"),
                 'package_information' : self.get_pkg_information(pkg),
                 'maintainance_time' : self.get_maintainance_time(pkg),
                 'action_button_description' : self.get_action_button_description(pkg),
               }
        
        self._load()
        self._substitute(subs)
        self._render()
        self.emit("selected", appname, pkg)

    def get_homepage_button_visibility(self):
        if self.homepage_url:
            return "visible"
        return "hidden"

    def get_pkg_information(self, pkg):
        if not pkg or not pkg.candidate:
            return ""
        version = pkg.candidate.version
        if version:
            s = _("Version: %s (%s)") % (version, pkg.name)
            return s
        return ""

    def get_maintainance_time(self, pkg):
        """add the end of the maintainance time"""
        # FIXME: add code
        return ""

    def get_action_button_description(self, pkg):
        """Add message specific to this package (e.g. how many dependenies"""
        s = ""
        if not pkg:
            return s
        # its installed, tell about rdepends
        if pkg.installed:
            # generic message
            s = _("%s is installed on this computer.") % self.appname
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
        return s

    # callbacks
    def on_button_enable_channel_clicked(self):
        #print "on_enable_channel_clicked"
        # FIXME: move this to utilities or something
        import aptsources.sourceslist

        # read channel file and add all relevant lines
        for line in open(self.channelfile):
            line = line.strip()
            if not line:
                continue
            entry = aptsources.sourceslist.SourceEntry(line)
            if entry.invalid:
                continue
            sourcepart = os.path.basename(self.channelfile)
            try:
                self.aptd_client.add_repository(
                    entry.type, entry.uri, entry.dist, entry.comps, 
                    "Added by software-store", sourcepart)
            except dbus.exceptions.DBusException, e:
                if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                    return
        # FIXME: make the button in-sensitve (maybe directly in the html/JS?)
        #widget.set_sensitive(False)
        trans = self.aptd_client.update_cache(
            exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_homepage_clicked(self):
        cmd = self._url_launch_app()
        subprocess.call([cmd, self.homepage_url])

    def on_button_upgrade_clicked(self):
        trans = self.aptd_client.commit_packages([], [], [], [], [self.pkgname], 
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_remove_clicked(self):
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

    def on_button_install_clicked(self):
        trans = self.aptd_client.commit_packages([self.pkgname], [], [], [], [],
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

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

    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-store"

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    
    cache = apt.Cache()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsView(db, icons, cache, datadir)
    #view.show_app("AMOR")
    #view.show_app("3D Chess")
    view.show_app("Configuration Editor")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
