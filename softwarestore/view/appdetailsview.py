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
import tempfile
import time
import xapian

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
 
from gettext import gettext as _

from widgets.wkwidget import WebkitWidget
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
    APP_ICON_SIZE = 64
    APP_ICON_PADDING = 8

    # dependency types we are about
    DEPENDENCY_TYPES = ("PreDepends", "Depends", "Recommends")
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (str,str, ))
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
        
    def _show(self, widget):
        if not self.appname:
            return
        super(AppDetailsView, self)._show(widget)

    # public API
    def show_app(self, appname):
        logging.debug("AppDetailsView.show_app '%s'" % appname)
        
        # clear first to avoid showing the old app details for
        # some milliseconds before switching to the new app 
        self.clear()

        # init app specific data
        self.appname = appname
        self.installed_rdeps = set()
        self.homepage_url = None
        self.channelfile = None
        self.doc = None

        # get xapian document
        for m in self.xapiandb.postlist("AA"+appname):
            self.doc = self.xapiandb.get_document(m.docid)
            break
        if not self.doc:
            raise IndexError, "No app '%s' in database" % appname

        # get icon
        self.iconname = self.doc.get_value(XAPIAN_VALUE_ICON)

        # get apt cache data
        self.pkgname = self.doc.get_value(XAPIAN_VALUE_PKGNAME)
        self.pkg = None
        if self.cache.has_key(self.pkgname):
            self.pkg = self.cache[self.pkgname]
        if self.pkg:
            self.homepage_url = self.pkg.candidate.homepage

        # show (and let the wksub_ magic do the right substitutions)
        self._show(self)
        self.emit("selected", self.appname, self.pkgname)

    def clear(self):
        " clear the current view "
        self.load_string("","text/plain","ascii","file:/")
        while gtk.events_pending(): 
            gtk.main_iteration()

    # substitute functions called during page display
    def wksub_appname(self):
        return self.appname
    def wksub_pkgname(self):
        return self.pkgname
    def wksub_iconname(self):
        return self.iconname
    def wksub_body_class(self):
        if (self.cache.has_key(self.pkgname) and
            self.cache[self.pkgname].isInstalled):
            return "section-installed"
        return "section-get"
    def wksub_description(self):
        if self.pkg:
            details = self.pkg.candidate.description
        else:
            details = _("Not available in the current data")
        description = details.replace("*","</p><p>*")
        description = description.replace("\n-","</p><p>-")
        description = description.replace("\n\n","</p><p>")
        return description
    def wksub_iconpath_loading(self):
        # FIXME: use relative path here
        return "/usr/share/icons/hicolor/32x32/animations/software-store-loading.gif"
    def wksub_iconpath(self):
        # the iconname in the theme is without extension
        iconname = os.path.splitext(self.iconname)[0]
        iconinfo = self.icons.lookup_icon(iconname, 
                                          self.APP_ICON_SIZE, 0)
        if iconinfo:
            iconpath = iconinfo.get_filename()
        else:
            iconpath = self.MISSING_ICON_PATH
        # *meh* if not png -> convert
        # FIXME: make webkit understand xpm files instead
        if iconpath.endswith(".xpm"):
            self.tf = tempfile.NamedTemporaryFile()
            pix = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
            pix.save(self.tf.name, "png")
            iconpath = self.tf.name
        return iconpath
    def wksub_software_installed_icon(self):
        # FIXME: use relative path here
        return "/usr/share/icons/hicolor/24x24/emblems/software-store-installed.png"
    def wksub_icon_width(self):
        return self.APP_ICON_SIZE
    def wksub_icon_height(self):
        return self.APP_ICON_SIZE
    def wksub_action_button_label(self):
        return self._get_action_button_label_and_value()[0]
    def wksub_action_button_value(self):
        return self._get_action_button_label_and_value()[1]
    def wksub_action_button_visible(self):
        if not self.channelfile and not self.pkg:
            return "hidden"
        return "visible"
    def wksub_homepage_button_visibility(self):
        if self.homepage_url:
            return "visible"
        return "hidden"
    def wksub_package_information(self):
        if not self.pkg or not self.pkg.candidate:
            return ""
        version = self.pkg.candidate.version
        if version:
            s = _("Version: %s (%s)") % (version, self.pkg.name)
            return s
        return ""
    def wksub_datadir(self):
        return self.datadir
    def wksub_maintainance_time(self):
        """add the end of the maintainance time"""
        # FIXME: add code
        return ""
    def wksub_action_button_description(self):
        """Add message specific to this package (e.g. how many dependenies"""
        s = ""
        if not self.pkg:
            return s
        # its installed, tell about rdepends
        pkg = self.pkg
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
    def wksub_homepage(self):
        s = _("Website")
        return s
    def wksub_price(self):
        s = _("Price: %s") % _("Free")
        return s
    def wksub_installed(self):
        if self.pkg and self.pkg.installed:
            return "visible"
        return "hidden"
    def wksub_screenshot_installed(self):
        if (self.cache.has_key(self.pkgname) and
            self.cache[self.pkgname].isInstalled):
            return "screenshot_thumbnail-installed"
        return "screenshot_thumbnail"
        
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

    # public interface
    def install(self):
        self.on_button_install_clicked()
    def remove(self):
        self.on_button_remove_clicked()
    def upgrade(self):
        self.on_button_upgrade_clicked()

    # internal callback
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
    def _get_action_button_label_and_value(self):
        action_button_label = ""
        action_button_value = ""
        if self.pkg:
            pkg = self.pkg
            if pkg.installed and pkg.isUpgradable:
                action_button_label = _("Upgrade")
                action_button_value = "upgrade"
            elif pkg.installed:
                action_button_label = _("Remove")
                action_button_value = "remove"
            else:
                action_button_label = _("Install")
                action_button_value = "install"
        elif self.doc:
            channel = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            if channel:
                path = APP_INSTALL_CHANNELS_PATH + channel +".list"
                if os.path.exists(path):
                    self.channelfile = path
                    # FIXME: deal with the EULA stuff
                    action_button_label = _("Enable channel")
                    action_button_value = "enable_channel"
        return (action_button_label, action_button_value)

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

    xapian_base_path = "/var/cache/software-store"
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
    #view.show_app("Configuration Editor")
    #view.show_app("ACE")
    #view.show_app("Artha")
    #view.show_app("cournol")
    view.show_app("Qlix")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    gtk.main()
