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
import gettext
import glib
import gobject
import gtk
import json
import logging
import os
import re
import socket
import string
import subprocess
import sys
import tempfile
import threading
import urllib
import xapian

from gettext import gettext as _

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

from softwarecenter.enums import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase, Application

# make review feature testing easy
if "SOFTWARE_CENTER_IPSUM_REVIEWS" in os.environ:
    from softwarecenter.db.reviews import ReviewLoaderIpsum as ReviewLoader
else:
    from softwarecenter.db.reviews import ReviewLoaderXMLAsync as ReviewLoader

from softwarecenter.backend.aptd import AptdaemonBackend as InstallBackend

from widgets.wkwidget import WebkitWidget
from widgets.imagedialog import ShowImageDialog, GnomeProxyURLopener, Url404Error, Url403Error
import dialogs

# default socket timeout to deal with unreachable screenshot site
DEFAULT_SOCKET_TIMEOUT=4

class AppDetailsView(WebkitWidget):
    """The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 64
    APP_ICON_PADDING = 8

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/software-center/emblems/software-center-installed.png"
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (str,str, ))
                    }

    def __init__(self, db, distro, icons, cache, datadir):
        super(AppDetailsView, self).__init__(datadir)
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.datadir = datadir
        self.arch = subprocess.Popen(["dpkg","--print-architecture"], 
                                     stdout=subprocess.PIPE).communicate()[0].strip()
        self.review_loader = ReviewLoader()
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # aptdaemon
        self.backend = InstallBackend()
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        # data
        self.appname = ""
        self.pkgname = ""
        self.iconname = ""
        # setup user-agent
        settings = self.get_settings()
        settings.set_property("user-agent", USER_AGENT)
        self.connect("navigation-requested", self._on_navigation_requested)

    def _show(self, widget):
        if not self.appname:
            return
        super(AppDetailsView, self)._show(widget)

    # public API
    def init_app(self, appname, pkgname):
        logging.debug("AppDetailsView.init_app '%s'" % appname)
        # init app specific data
        self.appname = appname
        # if we don't have a app, we use the pkgname as appname
        if not appname:
            self.appname = pkgname
        # other data
        self.homepage_url = None
        self.channelfile = None
        self.channelname = None
        self.doc = None

        # get xapian document
        self.doc = self.db.get_xapian_document(appname, pkgname)
        if not self.doc:
            raise IndexError, "No app '%s' for '%s' in database" % (appname, pkgname)

        # get icon
        self.iconname = self.doc.get_value(XAPIAN_VALUE_ICON)
        # remove extension (e.g. .png) because the gtk.IconTheme
        # will find fins a icon with it
        self.iconname = os.path.splitext(self.iconname)[0]

        # get apt cache data
        self.pkgname = self.db.get_pkgname(self.doc)
        self.component = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        self.pkg = None
        if (self.cache.has_key(self.pkgname) and
            self.cache[self.pkgname].candidate):
            self.pkg = self.cache[self.pkgname]
        if self.pkg:
            self.homepage_url = self.pkg.candidate.homepage
    
    def show_app(self, appname, pkgname):
        logging.debug("AppDetailsView.show_app '%s'" % appname)

        # clear first to avoid showing the old app details for
        # some milliseconds before switching to the new app
        self.clear()
        
        # initialize the app
        self.init_app(appname, pkgname)
        
        # show (and let the wksub_ magic do the right substitutions)
        self._show(self)
        self.emit("selected", self.appname, self.pkgname)
        # FIXME: this 404 checking code is all ugly and should be
        #        factored out
        # check for thumbnail (does a http HEAD so needs to run in
        # a extra thread to avoid blocking on connect)
        self._thumbnail_is_missing = False
        self._thumbnail_checking_thread_running = True
        threading.Thread(target=self._check_thumb_available).start()
        # also start a gtimeout handler to check when the thread finished
        # (multiple GUI access is something that gtk does not like)
        glib.timeout_add(200, self._check_thumb_gtk)
        # do a async review lookup
        glib.timeout_add(200, self._check_for_reviews)

    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    def clear(self):
        " clear the current view "
        self.load_string("", "text/plain", "ascii", "file:/")
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
        # if we do not have a package in our apt data explain why
        if not self.pkg:
            if self.channelname:
                return _("This software is available from the '%s' source, "
                         "which you are not currently using.") % self.channelname
            # if we have no pkg, check if its available for the given
            # architecture
            if self._available_for_our_arch():
                return _("To show information about this item, "
                         "the software catalog needs updating.")
            else:
                return _("Sorry, '%s' is not available for "
                         "this type of computer (%s).") % (
                        self.appname, self.arch)

        # format for html
        description = self.pkg.description
        #print description

        # format bullets (*-) as lists
        regx = re.compile("\n\s*([*-]+) (.*)")
        description = re.sub(regx, r'<li>\2</li>', description)
        description = self.add_ul_tags(description)
        
        #line breaks
        regx = re.compile("(\n\n)")
        description = re.sub(regx, r'<p></p>', description)
        
        # urls
        regx = re.compile("((ftp|http|https):\/\/[a-zA-Z0-9\/\\\:\?\%\.\&\;=#\-\_\!\+\~]*)")
        
        return re.sub(regx, r'<a href="\1">\1</a>', description)

    def add_ul_tags(self, description):
        n = description.find("<li>")
        if not n == -1:
            description[n:n+3].replace("<li>", "<ul><li>")
            description = description[0:n] + description[n:n+3].replace("<li>", "<ul><li>") + description[n+3:]
            description_list_tmp = []
            len_description = range(len(description))
            len_description.reverse()
        
            for letter in len_description:
                description_list_tmp.append(description[letter])
                
            description_list_tmp = "".join(description_list_tmp)
            n = len(description) - description_list_tmp.find(">il/<")
            return description[0:n] + description[n-5:n].replace("</li>", "</li></ul>") + description[n:]
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
        if os.path.exists(iconpath) and iconpath.endswith(".xpm"):
            self.tf = tempfile.NamedTemporaryFile()
            pix = self.icons.load_icon(self.iconname, self.APP_ICON_SIZE, 0)
            pix.save(self.tf.name, "png")
            iconpath = self.tf.name
        return iconpath
    def wksub_screenshot_thumbnail_url(self):
        url = self.distro.SCREENSHOT_THUMB_URL % self.pkgname
        return url
    def wksub_screenshot_alt(self):
        return _("Application Screenshot")
    def wksub_software_installed_icon(self):
        return self.INSTALLED_ICON
    def wksub_screenshot_alt(self):
        return _("Application Screenshot")
    def wksub_new_review_label_text(self):
        return _("Write new review")
    def wksub_report_abuse_label(self):
        return _("Report")
    def wksub_review_summary_stars_base_path(self):
        return self.distro.REVIEW_SUMMARY_STARS_BASE_PATH
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
        if (not self.channelfile and 
            not self.pkg and 
            not self._available_for_our_arch()):
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
        return self.distro.get_maintenance_status(self.cache,
            self.appname, self.pkgname, self.component, self.channelfile)
    def wksub_action_button_description(self):
        """Add message specific to this package (e.g. how many dependenies"""
        if not self.pkg:
            return ""
        return self.distro.get_rdepends_text(self.cache, self.pkg, self.appname)
    def wksub_homepage(self):
        s = _("Website")
        return s
    def wksub_license(self):
        return self.distro.get_license_text(self.component)
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
        return self.distro.IMAGE_THUMBNAIL_MISSING
    def wksub_text_direction(self):
        direction = gtk.widget_get_default_direction()
        if direction ==  gtk.TEXT_DIR_RTL:
            return 'DIR="RTL"'
        elif direction ==  gtk.TEXT_DIR_LTR:
            return 'DIR="LTR"'
    def wksub_font_family(self):
        return self._get_font_description_property("family")
    def wksub_font_weight(self):
        try:
            return self._get_font_description_property("weight").real
        except:
            return int(self._get_font_description_property("weight"))
    def wksub_font_style(self):
        return self._get_font_description_property("style").value_nick
    def wksub_font_size(self):
        return self._get_font_description_property("size")/1024


    # callbacks
    def on_button_reload_clicked(self):
        self.backend.reload()
        self._set_action_button_sensitive(False)

    def on_write_new_review_clicked(self):
        print "on_write_new_review_clicked"
        dialogs.error(None, "new review not implemented yet","")
    def on_report_abuse_clicked(self):
        print "on_report_abuse_clicked"
        dialogs.error(None, "report abuse not implemented yet","")
    def on_button_enable_channel_clicked(self):
        #print "on_enable_channel_clicked"
        # FIXME: move this to utilities or something
        self.backend.enable_channel(self.channelfile)
        self._set_action_button_sensitive(False)

    def on_screenshot_thumbnail_clicked(self):
        url = self.distro.SCREENSHOT_LARGE_URL % self.pkgname
        title = _("%s - Screenshot") % self.appname
        d = ShowImageDialog(
            title, url,
            self.icons.lookup_icon("process-working", 32, ()).get_filename(),
            self.icons.lookup_icon("process-working", 32, ()).get_base_size(),
            self.distro.IMAGE_FULL_MISSING)
        d.run()
        d.destroy()

    def on_button_homepage_clicked(self):
        cmd = self._url_launch_app()
        subprocess.call([cmd, self.homepage_url])

    def on_button_upgrade_clicked(self):
        self.upgrade()

    def on_button_remove_clicked(self):
        # generic removal text
        # FIXME: this text is not accurate, we look at recommends as
        #        well as part of the rdepends, but those do not need to
        #        be removed, they just may be limited in functionatlity
        (primary, button_text) = self.distro.get_removal_warning_text(self.cache, self.pkg, self.appname)

        # ask for confirmation if we have rdepends
        depends = self.cache.get_installed_rdepends(self.pkg)
        if depends:
            iconpath = self.get_icon_filename(self.iconname, self.APP_ICON_SIZE)
            
            if not dialogs.confirm_remove(None, primary, self.cache,
                                        button_text, iconpath, depends):
                self._set_action_button_sensitive(True)
                return
        self.remove()

    def on_button_install_clicked(self):
        self.install()

    # public interface
    def install(self):
        self.backend.install(self.pkgname, self.appname, self.iconname)
        self._set_action_button_sensitive(False)
    def remove(self):
        self.backend.remove(self.pkgname, self.appname, self.iconname)
        self._set_action_button_sensitive(False)
    def upgrade(self):
        self.backend.upgrade(self.pkgname, self.appname, self.iconname)
        self._set_action_button_sensitive(False)

    # internal callback
    def _on_transaction_finished(self, backend, success):
        # re-open cache and refresh app display
        self.cache.open()
        self.show_app(self.appname, self.pkgname)
    def _on_transaction_stopped(self, backend):
        self._set_action_button_sensitive(True)

    def _on_navigation_requested(self, view, frame, request):
        logging.debug("_on_navigation_requested %s" % request.get_uri())
        # not available in the python bindings yet
        # typedef enum {
        #  WEBKIT_NAVIGATION_RESPONSE_ACCEPT,
        #  WEBKIT_NAVIGATION_RESPONSE_IGNORE,
        #  WEBKIT_NAVIGATION_RESPONSE_DOWNLOAD
        # } WebKitNavigationResponse;
        uri = request.get_uri()
        if uri.startswith("http:") or uri.startswith("https:") or uri.startswith("www"):
            subprocess.call(["xdg-open", uri])
            return 1
        return 0

    # internal helpers
    def _check_for_reviews(self):
        logging.debug("_check_for_reviews")
        app = Application(self.appname, self.pkgname)
        reviews = self.review_loader.get_reviews(app, 
                                                 self._reviews_ready_callback)

    def _reviews_ready_callback(self, app, reviews):
        if not reviews:
            no_review = _("This software item has no reviews yet.")
            s='document.getElementById("reviews").innerHTML="%s"' % no_review
            self.execute_script(s)
        for review in reviews:
            # use json.dumps() here to let it deal with all the escaping
            # of ", \, \n etc
            s = 'addReview(%s, %s,%s,%s,%s,%s);' % (json.dumps(review.summary),
                                                    json.dumps(review.text),
                                                    json.dumps(review.id), 
                                                    json.dumps(review.date), 
                                                    json.dumps(review.rating), 
                                                    json.dumps(review.person))
            #logging.debug("running '%s'" % s)
            # FIXME: ensure webkit is in WEBKIT_LOAD_FINISHED state
            self.execute_script(s)
        return False

    def _check_thumb_gtk(self):
        logging.debug("_check_thumb_gtk")
        # wait until its ready for JS injection
        # 2 == WEBKIT_LOAD_FINISHED - the enums is not exposed via python
        if self.get_property("load-status") != 2:
            return True
        if self._thumbnail_is_missing:
            self.execute_script("thumbMissing();")
        return self._thumbnail_checking_thread_running

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
        timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(DEFAULT_SOCKET_TIMEOUT)
        urllib._urlopener = GnomeProxyURLopener()
        try:
            f = urllib.urlopen(self.distro.SCREENSHOT_THUMB_URL % self.pkgname)
        except (Url404Error, IOError), e:
            logging.debug("no thumbnail image")
            self._thumbnail_is_missing = True
        socket.setdefaulttimeout(timeout)
        self._thumbnail_checking_thread_running = False

    def _get_action_button_label_and_value(self):
        action_button_label = ""
        action_button_value = ""
        if self.pkg:
            pkg = self.pkg
            # Don't handle upgrades yet
            #if pkg.installed and pkg.isUpgradable:
            #    action_button_label = _("Upgrade")
            #    action_button_value = "upgrade"
            if pkg.installed:
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
                    self.channelname = channel
                    self.channelfile = path
                    # FIXME: deal with the EULA stuff
                    action_button_label = _("Use This Source")
                    action_button_value = "enable_channel"
            elif self._available_for_our_arch():
                action_button_label = _("Update Now")
                action_button_value = "reload"
        return (action_button_label, action_button_value)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)
        # if we don't have a arch entry in the document its available
        # on all architectures we know about
        if not arches:
            return True
        # check the arch field
        for arch in map(string.strip, arches.split(",")):
            if arch == self.arch:
                return True
        return False
    def _set_action_button_sensitive(self, enabled):
        if enabled:
            self.execute_script("enable_action_button();")
        else:
            self.execute_script("disable_action_button();")

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
        
    def _get_pango_font_description(self):
        return gtk.Label("pango").get_pango_context().get_font_description()
        
    def _get_font_description_property(self, property):
        description = self._get_pango_font_description()
        return getattr(description, "get_%s" % property)()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache()
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsView(db, distro, icons, cache, datadir)
    #view.show_app("3D Chess", "3dchess")
    view.show_app("Movie Player", "totem")
    #view.show_app("ACE", "unace")

    #view.show_app("AMOR")
    #view.show_app("Configuration Editor")
    #view.show_app("Artha")
    #view.show_app("cournol")
    #view.show_app("Qlix")

    win = gtk.Window()
    scroll.add(view)
    win.add(scroll)
    win.set_size_request(600,600)
    win.show_all()

    #view._config_file_prompt(None, "/etc/fstab", "/tmp/lala")

    gtk.main()
