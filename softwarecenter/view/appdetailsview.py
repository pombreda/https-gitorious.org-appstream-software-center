# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
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
import glib
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
import threading
import xapian
import urllib

from aptdaemon import policykit1
from aptdaemon import client
from aptdaemon import enums
from aptdaemon.gtkwidgets import AptMediumRequiredDialog
 
from gettext import gettext as _

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")
from softwarecenter.enums import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase

from widgets.wkwidget import WebkitWidget
from widgets.imagedialog import ShowImageDialog, GnomeProxyURLopener, Url404Error, Url403Error
import dialogs

class AppDetailsView(WebkitWidget):
    """The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 64
    APP_ICON_PADDING = 8

    # dependency types we are about
    # FIXME: we do not support warning about removal of stuff that is
    #        recommended because its not speced
    DEPENDENCY_TYPES = ("PreDepends", "Depends") #, "Recommends")
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    SCREENSHOT_THUMB_URL =  "http://screenshots.debian.net/thumbnail-404/%s"
    SCREENSHOT_LARGE_URL = "http://screenshots.debian.net/screenshot-404/%s"

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/icons/hicolor/24x24/emblems/software-center-installed.png"
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"
    
    # missing thumbnail
    IMAGE_THUMBNAIL_MISSING = "/usr/share/software-center/images/dummy-thumbnail-ubuntu.png"
    IMAGE_FULL_MISSING = "/usr/share/software-center/images/dummy-screenshot-ubuntu.png"


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
        self.arch = subprocess.Popen(["dpkg","--print-architecture"], 
                                     stdout=subprocess.PIPE).communicate()[0]
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # aptdaemon
        self.aptd_client = client.AptClient()
        self.window_main_xid = None
        # data
        self.appname = ""
        self.pkgname = ""
        self.iconname = ""
        # setup missing icon
        iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, 
                                          self.APP_ICON_SIZE, 0)
        self.MISSING_ICON_PATH = iconinfo.get_filename()
        # setup user-agent
        settings = self.get_settings()
        settings.set_property("user-agent", USER_AGENT)

    def _show(self, widget):
        if not self.appname:
            return
        super(AppDetailsView, self)._show(widget)

    # public API
    def show_app(self, appname, pkgname):
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
        self.doc = self.xapiandb.get_xapian_document(appname, pkgname)
        if not self.doc:
            raise IndexError, "No app '%s' for '%s' in database" % (appname, pkgname)

        # get icon
        self.iconname = self.doc.get_value(XAPIAN_VALUE_ICON)
        # remove extension (e.g. .png) because the gtk.IconTheme
        # will find fins a icon with it
        self.iconname = os.path.splitext(self.iconname)[0]

        # get apt cache data
        self.pkgname = self.doc.get_value(XAPIAN_VALUE_PKGNAME)
        self.component = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        self.pkg = None
        if (self.cache.has_key(self.pkgname) and 
            self.cache[self.pkgname].candidate):
            self.pkg = self.cache[self.pkgname]
        if self.pkg:
            self.homepage_url = self.pkg.candidate.homepage

        # show (and let the wksub_ magic do the right substitutions)
        self._show(self)
        self.emit("selected", self.appname, self.pkgname)
        # check for thumbnail (does a http HEAD so needs to run in 
        # a extra thread to avoid blocking on connect)
        self._thumbnail_missing = False
        self._thumbnail_checking = True
        t=threading.Thread(target=self._check_thumb_available)
        t.start()
        #self._check_thumb_available()
        glib.timeout_add(200, self._check_thumb_gtk)

    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()
            
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
    def wksub_body_class(self):
        if (self.cache.has_key(self.pkgname) and
            self.cache[self.pkgname].isInstalled):
            return "section-installed"
        return "section-get"
    def wksub_description(self):
        if self.pkg:
            details = self.pkg.candidate.description
        else:
            # if we have no pkg, check if its available for the given
            # architecture
            arches = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)
            if arches:
                for arch in map(string.strip, arches.split(",")):
                    if arch == self.arch:
                        details = _("Not available in the current data")
                        break
                else:
                    details = _("Not available for your hardware architecture.")
            else:
                details = _("Not available in the current data")
        description = details.replace("*","</p><p>*")
        description = description.replace("\n-","</p><p>-")
        description = description.replace("\n\n","</p><p>")
        return description
    def wksub_iconpath_loading(self):
        if (self.cache.has_key(self.pkgname) and 
            self.cache[self.pkgname].isInstalled):
            return self.IMAGE_LOADING_INSTALLED
        return self.IMAGE_LOADING
    def wksub_iconpath(self):
        # the iconname in the theme is without extension
        iconpath = self.get_icon_filename(self.iconname, self.APP_ICON_SIZE)
        # *meh* if not png -> convert
        # FIXME: make webkit understand xpm files instead
        if iconpath.endswith(".xpm"):
            self.tf = tempfile.NamedTemporaryFile()
            pix = self.icons.load_icon(self.iconname, self.APP_ICON_SIZE, 0)
            pix.save(self.tf.name, "png")
            iconpath = self.tf.name
        return iconpath
    def wksub_screenshot_thumbnail_url(self):
        url = self.SCREENSHOT_THUMB_URL % self.pkgname
        return url
    def wksub_screenshot_alt(self):
        return _("Application Screenshot")
    def wksub_software_installed_icon(self):
        return self.INSTALLED_ICON
    def wksub_screenshot_alt(self):
        return _("Application Screenshot")
    def wksub_icon_width(self):
        return self.APP_ICON_SIZE
    def wksub_icon_height(self):
        return self.APP_ICON_SIZE
    def wksub_action_button_label(self):
        self.action_button_label = self._get_action_button_label_and_value()[0]
        return self.action_button_label
    def wksub_action_button_value(self):
        self.action_button_value = self._get_action_button_label_and_value()[1]
        return self.action_button_value
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
        return self.cache.get_maintenance_status(
            self.appname, self.pkgname, self.component, self.channelfile)
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
    def wksub_license(self):
        li =  _("Unknown")
        if self.component in ("main", "universe"):
            li = _("Open Source")
        elif self.component == "restricted":
            li = _("Proprietary")
        s = _("License: %s") % li
        return s
    def wksub_price(self):
	#TRANSLATORS: This text will be showed as price of the software
        price = _("Free")
	s = _("Price: %s") % price
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
    def wksub_screenshot_thumbnail_missing(self):
        return self.IMAGE_THUMBNAIL_MISSING
        
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
                    "Added by software-center", sourcepart)
            except dbus.exceptions.DBusException, e:
                if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                    return
        trans = self.aptd_client.update_cache(
            exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_screenshot_thumbnail_clicked(self):
        url = self.SCREENSHOT_LARGE_URL % self.pkgname
        title = _("%s - Screenshot") % self.appname
        d = ShowImageDialog(title, url, 
                            self.IMAGE_LOADING_INSTALLED,
                            self.IMAGE_FULL_MISSING)
        d.run()
        d.destroy()

    def on_button_homepage_clicked(self):
        cmd = self._url_launch_app()
        subprocess.call([cmd, self.homepage_url])

    def on_button_upgrade_clicked(self):
        trans = self.aptd_client.upgrade_packages([self.pkgname], 
                                          exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_remove_clicked(self):
        # generic removal text 
        # FIXME: this text is not accurate, we look at recommends as
        #        well as part of the rdepends, but those do not need to
        #        be removed, they just may be limited in functionatlity
        primary = _("To remove %s, these items must be removed "
                    "as well:" % self.appname)
        button_text = _("Remove All")
        depends = list(self.installed_rdeps)
        
        # alter it if a meta-package is affected
        for m in self.installed_rdeps:
            if self.cache[m].section == "metapackages":
                primary = _("If you uninstall %s, future updates will not "
                              "include new items in <b>%s</b> set. "
                              "Are you sure you want to continue?") % (self.appname, self.cache[m].installed.summary)
                button_text = _("Remove Anyway")
                depends = None
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in self.installed_rdeps:
                primary = _("%s is a core application in Ubuntu. "
                              "Uninstalling it may cause future upgrades "
                              "to be incomplete. Are you sure you want to "
                              "continue?") % self.appname
                button_text = _("Remove Anyway")
                depends = None
                break
                
        # ask for confirmation if we have rdepends
        if len(self.installed_rdeps):
            iconpath = self.get_icon_filename(self.iconname, self.APP_ICON_SIZE)
            if not dialogs.confirm_remove(None, primary, self.cache,
                                        button_text, iconpath, depends):
                self._set_action_button_sensitive(True)
                return

        # do it (no rdepends or user confirmed)
        trans = self.aptd_client.remove_packages([self.pkgname],
                                         exit_handler=self._on_trans_finished)
        self._run_transaction(trans)

    def on_button_install_clicked(self):
        trans = self.aptd_client.install_packages([self.pkgname],
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
    def _on_trans_reply(self):
        # dummy callback for now, but its required, otherwise the aptdaemon
        # client blocks the UI and keeps gtk from refreshing
        logging.debug("_on_trans_reply")

    def _on_trans_error(self, error):
        logging.warn("_on_trans_error: %s" % error)
        # re-enable the action button again if anything went wrong
        self._set_action_button_sensitive(True)
        if (error._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized" or 
            error._dbus_error_name == "org.freedesktop.DBus.Error.NoReply"):
            pass
        else:
            raise
    
    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        if enum == enums.EXIT_FAILED:
            excep = trans.get_error()
            msg = "%s: %s\n%s\n\n%s" % (
                   _("ERROR"),
                   enums.get_error_string_from_enum(excep.code),
                   enums.get_error_description_from_enum(excep.code),
                   excep.details)
            logging.error("error in _on_trans_finished '%s'" % msg)
            # show dialog to the user and exit (no need to reopen
            # the cache)
            dialogs.error(None, 
                          enums.get_error_string_from_enum(excep.code),
                          enums.get_error_description_from_enum(excep.code),
                          excep.details)
            return
        # re-open cache and refresh app display
        self.cache.open()
        self.show_app(self.appname, self.pkgname)

    # internal helpers
    def _check_thumb_gtk(self):
        logging.debug("_check_thumb_gtk")
        # wait until its ready for JS injection
        # 2 == WEBKIT_LOAD_FINISHED - the enums is not exposed via python
        if self.get_property("load-status") != 2:
            return True
        if self._thumbnail_missing:
            self.execute_script("thumbMissing();")
        return self._thumbnail_checking
    def _check_thumb_available(self):
        """ check if the thumbnail image is available on the server 
            and alter the html if not
        """
        # we have to do the checking here and can not do it directly
        # inside the html (e.g. via xmlhttp) because the security
        # boundaries will not allow us to request a http:// uri
        # from a file:// html page
        logging.debug("_check_thumb_available")
        # check if we can get the thumbnail or just a 404
        urllib._urlopener = GnomeProxyURLopener()
        try:
            f = urllib.urlopen(self.SCREENSHOT_THUMB_URL % self.pkgname)
        except Url404Error:
            logging.debug("no thumbnail image")
            self._thumbnail_missing = True
        self._thumbnail_checking = False

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

    def _set_action_button_sensitive(self, enabled):
        if enabled:
            self.execute_script("enable_action_button();")
        else:
            self.execute_script("disable_action_button();")
            
    # FIXME: move this to a better place
    def _get_diff(self, old, new):
        if not os.path.exists("/usr/bin/diff"):
            return ""
        diff = subprocess.Popen(["/usr/bin/diff", 
                                 "-u",
                                 old, new], 
                                stdout=subprocess.PIPE).communicate()[0]
        return diff

    # FIXME: move this into aptdaemon/use the aptdaemon one
    def _config_file_prompt(self, transaction, old, new):
        diff = self._get_diff(old, new)
        d = dialogs.DetailsMessageDialog(None, 
                                         details=diff,
                                         type=gtk.MESSAGE_INFO, 
                                         buttons=gtk.BUTTONS_NONE)
        d.add_buttons(_("_Keep"), gtk.RESPONSE_NO,
                      _("_Replace"), gtk.RESPONSE_YES)
        d.set_default_response(gtk.RESPONSE_NO)
        text = _("Configuration file '%s' changed") % old
        desc = _("Do you want to use the new version?")
        d.set_markup("<big><b>%s</b></big>\n\n%s" % (text, desc))
        res = d.run()
        d.destroy()
        # send result to the daemon
        if res == gtk.RESPONSE_YES:
            transaction.config_file_prompt_answer(old, "replace")
        else:
            transaction.config_file_prompt_answer(old, "keep")

    def _medium_required(self, transaction, label, drive):
        dialog = AptMediumRequiredDialog(medium, drive)
        res = dialog.run()
        dialog.hide()
        if res == gtk.RESPONSE_OK:
            transaction.provide_medium(medium)
        else:
            transaction.cancel()

    def _run_transaction(self, trans):
        # set object data
        trans.set_data("appname", self.appname)
        trans.set_data("iconname", self.iconname)
        trans.set_data("pkgname", self.pkgname)
        # we support debconf
        trans.set_debconf_frontend("gnome")
        trans.connect("config-file-prompt", self._config_file_prompt)
        trans.connect("medium-required", self._medium_required)
        self._set_action_button_sensitive(False)
        trans.run(error_handler=self._on_trans_error,
                  reply_handler=self._on_trans_reply)

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
        datadir = "/usr/share/software-center"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname)

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsView(db, icons, cache, datadir)
    #view.show_app("AMOR")
    #view.show_app("3D Chess", "3dchess")
    #view.show_app("Configuration Editor")
    view.show_app("ACE", "unace")
    #view.show_app("Artha")
    #view.show_app("cournol")
    #view.show_app("Qlix")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,400)
    win.show_all()

    #view._config_file_prompt(None, "/etc/fstab", "/tmp/lala")

    gtk.main()
