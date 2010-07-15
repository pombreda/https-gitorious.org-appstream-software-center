# Copyright (C) 2010 Canonical
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

import gio
import glib
import gobject
import gtk
import logging
import re
import os
import subprocess
import sys
import tempfile


from gettext import gettext as _

from softwarecenter.db.application import Application
from softwarecenter.enums import USER_AGENT, MISSING_APP_ICON
from softwarecenter.view.appdetailsview import AppDetailsViewBase
from softwarecenter.utils import get_current_arch, htmlize_package_desc
from widgets.wkwidget import WebkitWidget

from widgets.imagedialog import ShowImageDialog


class AppDetailsViewWebkit(AppDetailsViewBase, WebkitWidget):
    """The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 64
    APP_ICON_PADDING = 8

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

    # hrm, can not put this into AppDetailsViewBase as it overrides
    # the webkit signals otherwise :/
    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT, )),
                    }
    

    def __init__(self, db, distro, icons, cache, history, datadir, viewport=None):
        AppDetailsViewBase.__init__(self, db, distro, icons, cache, history, datadir)
        WebkitWidget.__init__(self, datadir)
        self.arch = get_current_arch()
        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))
        # setup user-agent
        settings = self.get_settings()
        settings.set_property("user-agent", USER_AGENT)
        self.connect("navigation-requested", self._on_navigation_requested)
        # signals
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

    # public API
    def _draw(self):
        # clear first to avoid showing the old app details for
        # some milliseconds before switching to the new app
        self._clear()
        # show (and let the wksub_ magic do the right substitutions)
        self._show(self)
        # print "html: ", self._html
        self._check_thumb_available()
    
    def show_app(self, app):
        AppDetailsViewBase.show_app(self, app)

    # private stuff
    def _show(self, widget):
        if not (self.app or self.appdetails):
            return
        WebkitWidget._show(self, widget)
    def _clear(self):
        " clear the current view "
        self.load_string("", "text/plain", "ascii", "file:/")
        while gtk.events_pending(): 
            gtk.main_iteration()

    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    # substitute functions called during page display
    def wksub_appname(self):
        return self.app.name
    def wksub_summary(self):
        return self.appdetails.summary
    def wksub_pkgname(self):
        return self.app.pkgname
    def wksub_body_class(self):
        if self.appdetails.pkg and self.appdetails.pkg.is_installed:
            return "section-installed"
        return "section-get"
    def wksub_description(self):
        # FIXME: portme to AppDetails class
        if not self.appdetails.pkg:
            available_for_arch = self._available_for_our_arch()
            if self.appdetails.channelfile and available_for_arch:
                return _("This software is available from the '%s' source, "
                         "which you are not currently using.") % self.appdetails.channelname
            # if we have no pkg in the apt cache, check if its available for
            # the given architecture and if it has a component associated
            if available_for_arch and self.appdetails.component:
                return _("To show information about this item, "
                         "the software catalog needs updating.")
            
            # if we don't have a package and it has no arch/component its
            # not available for us
            return _("Sorry, '%s' is not available for "
                     "this type of computer (%s).") % (
                self.app.name, self.arch)
        # ---------------------------------------

        # format for html
        description = self.appdetails.description
        logging.debug("Description (text) %r", description)
        # format bullets (*-) as lists
        description = "\n".join(htmlize_package_desc(description))
        description = self.add_ul_tags(description)
        # urls
        regx = re.compile("((ftp|http|https):\/\/[a-zA-Z0-9\/\\\:\?\%\.\&\;=#\-\_\!\+\~]*)")
        description = re.sub(regx, r'<a href="\1">\1</a>', description)
        logging.debug("Description (HTML) %r", description)
        return description

    def add_ul_tags(self, description):
        """ add <ul></ul> around a bunch of <li></li> lists
        """
        first_li = description.find("<li>")
        last_li =  description.rfind("</li>")
        if first_li >= 0 and last_li >= 0:
            last_li += len("</li>")
            return '%s<ul tabindex="0">%s</ul>%s' % (
                description[:first_li],
                description[first_li:last_li],
                description[last_li:])
        return description

    def wksub_iconpath_loading(self):
        if (self.appdetails.pkg and self.appdetails.pkg.is_installed):
            return self.IMAGE_LOADING_INSTALLED
        return self.IMAGE_LOADING
    def wksub_iconpath(self):
        # the iconname in the theme is without extension
        iconname = self.appdetails.icon
        iconpath = self.get_icon_filename(iconname, self.APP_ICON_SIZE)
        # *meh* if not png -> convert
        # FIXME: make webkit understand xpm files instead
        if os.path.exists(iconpath) and iconpath.endswith(".xpm"):
            self.tf = tempfile.NamedTemporaryFile()
            pix = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
            pix.save(self.tf.name, "png")
            iconpath = self.tf.name
        return iconpath
    def wksub_screenshot_thumbnail_url(self):
        return self.appdetails.thumbnail
    def wksub_screenshot_large_url(self):
        return self.appdetails.screenshot
    def wksub_screenshot_alt(self):
        return _("Application Screenshot")
    def wksub_software_installed_icon(self):
        return self.INSTALLED_ICON
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
        if not self._available_for_our_arch():
            return "hidden"
        if (not self.appdetails.channelfile and 
            not self._unavailable_component() and
            not self.appdetails.pkg):
            return "hidden"
        return "visible"
    def wksub_homepage_button_visibility(self):
        if self.appdetails.website:
            return "visible"
        return "hidden"
    def wksub_share_button_visibility(self):
        if os.path.exists("/usr/bin/gwibber-poster"):
            return "visible"
        return "hidden"
    def wksub_package_information(self):
        if not self.appdetails.pkg:
            return ""
        version = self.appdetails.version
        if version:
            s = _("Version: %s (%s)") % (version, self.appdetails.pkgname)
            return s
        return ""
    def wksub_datadir(self):
        return self.datadir
    def wksub_maintainance_time(self):
        """add the end of the maintainance time"""
        return self.appdetails.maintenance_status
    def wksub_action_button_description(self):
        """Add message specific to this package (e.g. how many dependenies"""
        if self.appdetails.pkg and self.appdetails.pkg.installed:
            installed_date = self.appdetails.installation_date
            if installed_date:
                return _("Installed since %s") % installed_date.isoformat(" ")
            else:
                return _("Installed")
        return ""
    def wksub_homepage(self):
        s = _("Website")
        return s
    def wksub_share(self):
        s = _("Share via microblog")
        return s
    def wksub_license(self):
        return self.appdetails.license
    def wksub_price(self):
        return self.appdetails.price
    def wksub_installed(self):
        if self.appdetails.pkg and self.appdetails.pkg.installed:
            return "visible"
        return "hidden"
    def wksub_screenshot_installed(self):
        if self.appdetails.pkg and self.appdetails.pkg.is_installed:
            return "screenshot_thumbnail-installed"
        return "screenshot_thumbnail"
    def wksub_screenshot_thumbnail_missing(self):
        return self.distro.IMAGE_THUMBNAIL_MISSING
    def wksub_no_screenshot_avaliable(self):
        return _('No screenshot available')
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
        self.reload()
        self._set_action_button_sensitive(False)

    def on_button_enable_channel_clicked(self):
        #print "on_enable_channel_clicked"
        self.backend.enable_channel(self.appdetails.channelfile)
        self._set_action_button_sensitive(False)

    def on_button_enable_component_clicked(self):
        #print "on_enable_component_clicked", component
        component =  self.appdetails.component
        self.backend.enable_component(component)
        self._set_action_button_sensitive(False)

    def on_screenshot_thumbnail_clicked(self):
        url = self.distro.SCREENSHOT_LARGE_URL % self.app.pkgname
        title = _("%s - Screenshot") % self.app.name
        d = ShowImageDialog(
            title, url,
            self.distro.IMAGE_FULL_MISSING)
        d.run()
        d.destroy()

    def on_button_homepage_clicked(self):
        cmd = self._url_launch_app()
        subprocess.call([cmd, self.appdetails.website])

    def on_button_share_clicked(self):
        # TRANSLATORS: apturl:%(pkgname) is the apt protocol
        msg = _("Check out %(appname)s apt:%(pkgname)s") % {
            'appname' : self.app.appname, 
            'pkgname' : self.app.pkgname }
        p = subprocess.Popen(["gwibber-poster", "-w", "-m", msg])
        # setup timeout handler to avoid zombies
        glib.timeout_add_seconds(1, lambda p: p.poll() is None, p)

    def on_button_upgrade_clicked(self):
        self.upgrade()

    def on_button_remove_clicked(self):
        self.remove()

    def on_button_install_clicked(self):
        self.install()

    # internal callback
    def _on_transaction_started(self, backend):
        self._set_action_button_sensitive(False)
    def _on_transaction_stopped(self, backend):
        self._set_action_button_sensitive(True)
        if not self.app:
            return
        self.execute_script("showProgress(false);")
    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if not self.app or not self.app.pkgname == pkgname:
            return
        # 2 == WEBKIT_LOAD_FINISHED - the enums is not exposed via python
        if self.get_load_status() != 2:
            return
        self._set_action_button_sensitive(False)
        self.execute_script("showProgress(true);")
        if pkgname in backend.pending_transactions:
            self.execute_script("updateProgress(%s);" % progress)

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
    def _check_thumb_available(self):
        """ check for 404 on the given thumbnail image and run
            JS thumbMissing() if the thumb is not available
        """
        # internal helpers for the internal helper
        def thumb_query_info_async_callback(source, result):
            logging.debug("thumb_query_info_async_callback")
            try:
                result = source.query_info_finish(result)
                self.execute_script("showThumbnail();")
            except glib.GError, e:
                logging.debug("no thumb available")
                glib.timeout_add(200, run_thumb_missing_js)
            del source
        def run_thumb_missing_js():
            logging.debug("run_thumb_missing_js")
            # wait until its ready for JS injection
            # 2 == WEBKIT_LOAD_FINISHED - the enums is not exposed via python
            if self.get_load_status() != 2:
                return True
            # we don't show "thumb-missing" anymore
            #self.execute_script("thumbMissing();"
            return False
        # use gio (its so nice)
        url = self.distro.SCREENSHOT_THUMB_URL % self.app.pkgname
        logging.debug("_check_thumb_available '%s'" % url)
        f=gio.File(url)
        f.query_info_async(gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                           thumb_query_info_async_callback)

    def _get_action_button_label_and_value(self):
        action_button_label = ""
        action_button_value = ""
        if self.appdetails.pkg:
            pkg = self.appdetails.pkg
            # Don't handle upgrades yet
            #if pkg.installed and pkg.isUpgradable:
            #    action_button_label = _("Upgrade")
            #    action_button_value = "upgrade"
            if pkg.installed:
                action_button_label = _("Remove")
                action_button_value = "remove"
            else:
                price = self.appdetails.price
                # we don't have price information
                if price is None:
                    action_button_label = _("Install")
                # its free
                elif price == _("Free"):
                    action_button_label = _("Install - Free")
                else:
                    # FIXME: string freeze, so d
                    #action_button_label = _("Install - %s") % price
                    logging.error("Can not handle price %s" % price)
                action_button_value = "install"
        # FIXME: use a state from the appdetails class here
        elif self.appdetails._doc:
            channelfile = self.appdetails.channelfile
            if channelfile:
                # FIXME: deal with the EULA stuff
                action_button_label = _("Use This Source")
                action_button_value = "enable_channel"
            # check if it comes from a non-enabled component
            elif self._unavailable_component():
                # FIXME: use a proper message here, but we are in string freeze
                action_button_label = _("Use This Source")
                action_button_value = "enable_component"
            elif self._available_for_our_arch():
                action_button_label = _("Update Now")
                action_button_value = "reload"
        return (action_button_label, action_button_value)

    def _unavailable_component(self):
        """ 
        check if the given doc refers to a component (like universe)
        that is currently not enabled
        """
        component =  self.appdetails.component
        logging.debug("component: '%s'" % component)
        # if there is no component accociated, it can not be unavailable
        if not component:
            return False
        distro_codename = self.distro.get_codename()
        available = self.cache.component_available(distro_codename, component)
        return (not available)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.appdetails.architecture
        # if we don't have a arch entry in the document its available
        # on all architectures we know about
        if not arches:
            return True
        # check the arch field and support both "," and ";"
        sep = ","
        if ";" in arches:
            sep = ";"
        elif "," in arches:
            sep = ","
        for arch in map(string.strip, arches.split(sep)):
            if arch == self.arch:
                return True
        return False
    def _set_action_button_sensitive(self, enabled):
        if self.get_load_status() != 2:
            return
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
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()

    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    from softwarecenter.apt.apthistory import get_apt_history
    history = get_apt_history()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsViewWebkit(db, distro, icons, cache, history, datadir)
    #view.show_app(Application("3D Chess", "3dchess"))
    view.show_app(Application("Movie Player", "totem"))
    #view.show_app(Application("ACE", "unace"))
    #view.show_app(Application("", "2vcard"))

    #view.show_app("AMOR")
    #view.show_app("Configuration Editor")
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
