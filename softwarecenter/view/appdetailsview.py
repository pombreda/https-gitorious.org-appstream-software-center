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
import gio
import glib
import gobject
import gtk
import logging
import os
import re
import socket
import string
import subprocess
import sys
import tempfile
import urllib
import xapian
import pango

from gettext import gettext as _

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

from softwarecenter import Application
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase
from softwarecenter.backend import get_install_backend

from widgets.imagedialog import ShowImageDialog, GnomeProxyURLopener, Url404Error, Url403Error
import dialogs

from widgets import mkit

# default socket timeout to deal with unreachable screenshot site
DEFAULT_SOCKET_TIMEOUT=4


# installed colours, taken from synaptic
COLOR_RED_LIGHT     = '#FF9595'
COLOR_RED_NORMAL    = '#EF2929'
COLOR_GREEN_LIGHT   = '#C3FF89'
COLOR_GREEN_NORMAL  = '#8AE234'
COLOR_BLACK         = '#323232'


class AppDetailsView(gtk.ScrolledWindow):
    """The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE       = gtk.ICON_SIZE_DIALOG

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
                    }

    def __init__(self, db, distro, icons, cache, history, datadir):
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.set_shadow_type(gtk.SHADOW_NONE)

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox = gtk.VBox(spacing=mkit.SPACING_SMALL)
        self.vbox.set_border_width(mkit.BORDER_WIDTH_LARGE)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.vbox)
        self.add(viewport)
        self.vbox.set_redraw_on_allocate(False)
        self.show_all()

        # framed section that contains all app details
        self.app_info = mkit.FramedSection()
        self.app_info.header.set_spacing(mkit.SPACING_LARGE)
        self.app_info.footer.set_size_request(-1, 2*mkit.EM)
        self.app_info.header.set_border_width(2*mkit.BORDER_WIDTH_LARGE)
        self.app_info.body.set_border_width(2*mkit.BORDER_WIDTH_LARGE)
        self.app_info.body.set_spacing(2*mkit.SPACING_LARGE)
        self.vbox.pack_start(self.app_info, False)

        # controls which are displayed if the app is installed
        installed = gtk.image_new_from_icon_name("software-center-installed",
                                                 gtk.ICON_SIZE_MENU)
        label = gtk.Label()
        markup = '<b><big><span color="%s">%s</span></big></b>' % (COLOR_BLACK, _('Installed'))
        label.set_markup(markup)
        self.remove_btn = gtk.Button(_('Remove'))

        self.action_bar = gtk.HBox()
        self.action_bar.set_spacing(mkit.SPACING_MED)
        self.action_bar.set_border_width(mkit.BORDER_WIDTH_MED)
        self.action_bar.pack_start(installed, False)
        self.action_bar.pack_start(label, False)
        self.action_bar.pack_end(self.remove_btn, False)
        self.app_info.body.pack_start(self.action_bar, False)

        # vbox which contains textual paragraphs and bullet points
        self.app_desc = gtk.VBox(spacing=mkit.SPACING_SMALL)
        self.app_info.body.pack_start(self.app_desc)

        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))

        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.history = history

        self.datadir = datadir
        self.arch = get_current_arch()

        # aptdaemon
        self.backend = get_install_backend()
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

        # data
        self.pkg = None
        self.app = None
        self.iconname = ""

        self._paragraphs = []
        self._points = []

        viewport.connect('size-allocate', self._on_allocate)
        self.vbox.connect('expose-event', self._on_expose)
        return

    def _on_allocate(self, widget, allocation):
        w = allocation.width
        for p in self._paragraphs:
            p.set_size_request(w-6*mkit.EM, -1)
        for pt in self._points:
            pt.set_size_request(w-8*mkit.EM, -1)

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip()

        self.app_info.draw(cr, self.app_info.allocation, expose_area)

        # if installed draw border around installed controls
        self._draw_action_bar_bg(cr,
                                 COLOR_GREEN_LIGHT,
                                 COLOR_GREEN_NORMAL)

        del cr
        return

    def _full_redraw_cb(self):
        self.queue_draw()
        return False

    def _full_redraw(self):
        # If we relied on a single queue_draw newly exposed (previously
        # clipped) regions of the Viewport are blighted with
        # visual artefacts, so...

        # Two draws are queued; one immediately and one as an idle process

        # The immediate draw results in visual artefacts
        # but without which the resize feels 'laggy'.
        # The idle redraw cleans up the regions affected by 
        # visual artefacts.

        # This all seems to happen fast enough such that the user will
        # not to notice the temporary visual artefacts.  Peace out.

        self.queue_draw()
        gobject.idle_add(self._full_redraw_cb)
        return

    def _draw_action_bar_bg(self, cr, bg_color, line_color):
        a = self.action_bar.allocation
        rr = mkit.ShapeRoundedRectangle()

        rr.layout(cr,
                  a.x, a.y,
                  a.x+a.width, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(bg_color))
        cr.fill()

        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)

        rr.layout(cr,
                  a.x, a.y,
                  a.x+a.width, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(line_color))
        cr.stroke()
        cr.restore()
        return

    def _get_component(self, pkg=None):
        """ 
        get the component (main, universe, ..) for the given pkg object
        
        this uses the data from apt, if there is none it uses the 
        data from the app-install-data files
        """
        if not pkg or not pkg.candidate:
            return self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        for origin in pkg.candidate.origins:
            if (origin.origin == "Ubuntu" and 
                origin.trusted and 
                origin.component):
                return origin.component

    def _clear_description(self):
        for child in self.app_desc.get_children():
            self.app_desc.remove(child)
            child.destroy()

        self._paragraphs = []
        self._points = []
        return

    def _append_paragraph(self, fragment, newline):
        if not fragment.strip(): return
        p = gtk.Label()

        if newline:
            p.set_markup('\n'+fragment)
        else:
            p.set_markup(fragment)

        p.set_line_wrap(True)

        hb = gtk.HBox()
        hb.pack_start(p, False)
        hb.show_all()

        self.app_desc.pack_start(hb)
        self._paragraphs.append(p)
        return True

    def _append_bullet_point(self, fragment):
        fragment = fragment.strip()
        fragment = fragment.replace('* ', '')
        fragment = fragment.replace('- ', '')

        bullet = gtk.Label()
        bullet.set_markup(u" \u2022")
        bullet_align = gtk.Alignment(0.5, 0.0)
        bullet_align.add(bullet)

        point = gtk.Label()
        point.set_markup(fragment)
        point.set_line_wrap(True)

        hb = gtk.HBox(spacing=mkit.EM)
        hb.pack_start(bullet_align, False)
        hb.pack_start(point, False)
        hb.show_all()

        self.app_desc.pack_start(hb,
                                 padding=3)

        self._points.append(point)
        return False

    def _format_description(self, desc, appname):
        processed_desc = ''
        prev_part = ''
        parts = desc.split('\n')

        newline = False
        in_blist = False

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                pass
            elif part.startswith('* ') or part.startswith('- '):
                if not in_blist:
                    in_blist = True
                    newline = self._append_paragraph(processed_desc, newline)
                else:
                    newline = self._append_bullet_point(processed_desc)

                processed_desc = ''
                processed_desc += part

                # specialcase for 7zip
                if appname == '7zip' and \
                    (i+1) < len(parts) and parts[i+1].startswith('   '): #tab
                    processed_desc += '\n'

            elif prev_part.endswith('.'):
                if in_blist:
                    in_blist = False
                    newline = self._append_bullet_point(processed_desc)
                else:
                    newline = self._append_paragraph(processed_desc, newline)

                processed_desc = ''
                processed_desc += part

            elif not prev_part.endswith(',') and part[0].isupper():
                if in_blist:
                    in_blist = False
                    newline = self._append_bullet_point(processed_desc)
                else:
                    newline = self._append_paragraph(processed_desc, newline)

                processed_desc = ''
                processed_desc += part
            else:
                if not part.endswith('.'):
                    processed_desc += part + ' '
                elif (i+1) < len(parts) and (parts[i+1].startswith('* ') or \
                    parts[i+1].startswith('- ')):
                    processed_desc += part
                else:
                    processed_desc += part

            prev_part = part

        if in_blist:
            in_blist = False
            self._append_bullet_point(processed_desc)
        else:
            self._append_paragraph(processed_desc, newline)

        self.app_desc.show_all()
        return

    def _layout_page(self):
        # application icon and name packed into header
        font_size = 22*pango.SCALE  # make this relative to the appicon size (48x48)
        appname = self.get_appname()

        markup = '<b><span size="%s">%s</span></b>\n%s' % (font_size,
                                                           appname,
                                                           self.get_appsummary())

        self.app_info.set_label(markup=markup)
        self.app_info.set_icon(self.iconname, gtk.ICON_SIZE_DIALOG)

        self._clear_description()
        self._format_description(self.get_description(), appname)
        return

    # public API
    def show_app(self, app):
        logging.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            return

        # initialize the app
        self.init_app(app)
        
        #self._check_thumb_available()
        return

    def init_app(self, app):
        logging.debug("AppDetailsView.init_app '%s'" % app)

        # init app specific data
        self.app = app

        # other data
        self.homepage_url = None
        self.channelfile = None
        self.channelname = None
        self.doc = None

        # get xapian document
        self.doc = self.db.get_xapian_document(self.app.appname, 
                                               self.app.pkgname)
        if not self.doc:
            raise IndexError, "No app '%s' for '%s' in database" % (
                self.app.appname, self.app.pkgname)

        # get icon
        self.iconname = self.db.get_iconname(self.doc)
        # remove extension (e.g. .png) because the gtk.IconTheme
        # will find fins a icon with it
        self.iconname = os.path.splitext(self.iconname)[0]

        # get apt cache data
        pkgname = self.db.get_pkgname(self.doc)
        self.pkg = None
        if (pkgname in self.cache and
            self.cache[pkgname].candidate):
            self.pkg = self.cache[pkgname]
        if self.pkg:
            self.homepage_url = self.pkg.candidate.homepage

        # setup component
        self.component = self._get_component(self.pkg)

        self._layout_page()
        return

    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    # substitute functions called during page display
    def get_appname(self):
        return self.app.name
    def get_appsummary(self):
        return self.db.get_summary(self.doc)
    def wksub_pkgname(self):
        return self.app.pkgname
    def wksub_body_class(self):
        if (self.app.pkgname in self.cache and
            self.cache[self.app.pkgname].is_installed):
            return "section-installed"
        return "section-get"
    def get_description(self):
        # if we do not have a package in our apt data explain why
        if not self.pkg:
            available_for_arch = self._available_for_our_arch()
            if self.channelname and available_for_arch:
                return _("This software is available from the '%s' source, "
                         "which you are not currently using.") % self.channelname
            # if we have no pkg in the apt cache, check if its available for
            # the given architecture and if it has a component associated
            if available_for_arch and self.component:
                return _("To show information about this item, "
                         "the software catalog needs updating.")
            
            # if we don't have a package and it has no arch/component its
            # not available for us
            return _("Sorry, '%s' is not available for "
                     "this type of computer (%s).") % (
                self.app.name, self.arch)

        # format for html
        description = self.pkg.candidate.description
        logging.debug("Description (text) %r", description)
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
        if (self.app.pkgname in self.cache and
            self.cache[self.app.pkgname].is_installed):
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
        url = self.distro.SCREENSHOT_THUMB_URL % self.app.pkgname
        return url
    def wksub_screenshot_large_url(self):
        url = self.distro.SCREENSHOT_LARGE_URL % self.app.pkgname
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
        if not self._available_for_our_arch():
            return "hidden"
        if (not self.channelfile and 
            not self._unavailable_component() and
            not self.pkg):
            return "hidden"
        return "visible"
    def wksub_homepage_button_visibility(self):
        if self.homepage_url:
            return "visible"
        return "hidden"
    def wksub_share_button_visibility(self):
        if os.path.exists("/usr/bin/gwibber-poster"):
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
            self.app.appname or self.app.pkgname, self.app.pkgname, self.component, self.channelfile)
    def wksub_action_button_description(self):
        """Add message specific to this package (e.g. how many dependenies"""
        if not self.pkg:
            return ""
        return self.distro.get_installation_status(self.cache, self.history, self.pkg, self.app.name)
    def wksub_homepage(self):
        s = _("Website")
        return s
    def wksub_share(self):
        s = _("Share via microblog")
        return s
    def wksub_license(self):
        return self.distro.get_license_text(self.component)
    def wksub_price(self):
        price = self.distro.get_price(self.doc)
        s = _("Price: %s") % price
        return s
    def get_installed(self):
        if self.pkg and self.pkg.installed:
            return True
        return False
    def wksub_screenshot_installed(self):
        if (self.app.pkgname in self.cache and
            self.cache[self.app.pkgname].is_installed):
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
        self.backend.reload()
        self._set_action_button_sensitive(False)

    def on_button_enable_channel_clicked(self):
        #print "on_enable_channel_clicked"
        self.backend.enable_channel(self.channelfile)
        self._set_action_button_sensitive(False)

    def on_button_enable_component_clicked(self):
        #print "on_enable_component_clicked", component
        component =  self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        self.backend.enable_component(component)
        self._set_action_button_sensitive(False)

    def on_screenshot_thumbnail_clicked(self):
        url = self.distro.SCREENSHOT_LARGE_URL % self.app.pkgname
        title = _("%s - Screenshot") % self.app.name
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

    def on_button_share_clicked(self):
        # TRANSLATORS: apturl:%(pkgname) is the apt protocol
        msg = _("Check out %(appname)s apturl:%(pkgname)s") % {
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

    # public interface
    def install(self):
        self.backend.install(self.app.pkgname, self.app.appname, self.iconname)

    def remove(self):
        # generic removal text
        # FIXME: this text is not accurate, we look at recommends as
        #        well as part of the rdepends, but those do not need to
        #        be removed, they just may be limited in functionatlity
        (primary, button_text) = self.distro.get_removal_warning_text(self.cache, self.pkg, self.app.name)

        # ask for confirmation if we have rdepends
        depends = self.cache.get_installed_rdepends(self.pkg)
        if depends:
            iconpath = self.get_icon_filename(self.iconname, self.APP_ICON_SIZE)
            
            if not dialogs.confirm_remove(None, primary, self.cache,
                                        button_text, iconpath, depends):
                self._set_action_button_sensitive(True)
                self.backend.emit("transaction-stopped")
                return
        self.backend.remove(self.app.pkgname, self.app.appname, self.iconname)
    def upgrade(self):
        self.backend.upgrade(self.app.pkgname, self.app.appname, self.iconname)

    # internal callback
    def _on_cache_ready(self, cache):
        logging.debug("on_cache_ready")
        self.show_app(self.app)
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
                price = self.distro.get_price(self.doc)
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
        # FIXME: use self.component here instead?
        component =  self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        logging.debug("component: '%s'" % component)
        # if there is no component accociated, it can not be unavailable
        if not component:
            return False
        distro_codename = self.distro.get_codename()
        available = self.cache.component_available(distro_codename, component)
        return (not available)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)
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

    def _url_launch_app(self):
        """return the most suitable program for opening a url"""
        if "GNOME_DESKTOP_SESSION_ID" in os.environ:
            return "gnome-open"
        return "xdg-open"

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
