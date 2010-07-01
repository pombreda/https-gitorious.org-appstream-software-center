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


# action colours, taken from synaptic
# reds: used for pkg_status errors or warnings
COLOR_RED_FILL     = '#FF9595'
COLOR_RED_OUTLINE  = '#EF2929'

# yellows: some user action is required outside of install or remove
COLOR_YELLOW_FILL    = '#FFF5A3'
COLOR_YELLOW_OUTLINE = '#FCE94F'

# greens: used for pkg installed or available for install
# and no user actions required
COLOR_GREEN_FILL    = '#D1FFA4'
COLOR_GREEN_OUTLINE = '#8AE234'

# fixed black for action bar label, taken from Ambiance gtk-theme
COLOR_BLACK         = '#323232'


# pkg action state constants
PKG_STATE_INSTALLED     = 0
PKG_STATE_UNINSTALLED   = 1
PKG_STATE_UPGRADABLE    = 2
PKG_STATE_INSTALLING    = 3
PKG_STATE_REMOVING      = 4
PKG_STATE_UPGRADING     = 5
PKG_STATE_NEEDS_SOURCE  = 6
PKG_STATE_UNAVAILABLE   = 7
PKG_STATE_UNKNOWN       = 8


class PackageStatusBar(gtk.Alignment):
    
    def __init__(self, details_view):
        gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)
        self.set_size_request(-1, int(3.5*mkit.EM+0.5))
        self.set_padding(mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL,
                         mkit.SPACING_LARGE,
                         mkit.SPACING_LARGE)

        self.hbox = gtk.HBox(spacing=mkit.SPACING_LARGE)
        self.add(self.hbox)

        self.label = gtk.Label()
        self.button = gtk.Button()
        self.progress = gtk.ProgressBar()

        self.pkg_state = None
        self.details_view = details_view

        self.hbox.pack_start(self.label, False)
        self.hbox.pack_end(self.button, False)
        self.hbox.pack_end(self.progress, False)
        self.show_all()

        self.button.connect('size-allocate', self._on_button_size_allocate)
        self.button.connect('clicked', self._on_button_clicked, details_view)
        return

    def _on_button_size_allocate(self, button, allocation):
        # make the progress bar the same height as the button
        self.progress.set_size_request(12*mkit.EM,
                                       allocation.height)
        return

    def _on_button_clicked(self, button, details_view):
        state = self.pkg_state
        if state == PKG_STATE_INSTALLED:
            details_view.remove()
        elif state == PKG_STATE_UNINSTALLED:
            details_view.install()
        else:
            details_view.upgrade()
        return

    def set_label(self, label):
        m = '<b><big><span color="%s">%s</span></big></b>' % (COLOR_BLACK, label)
        self.label.set_markup(m)
        return

    def set_button_label(self, label):
        self.button.set_label(label)
        return

    def set_pkg_state(self, state):
        view = self.details_view
        self.pkg_state = state
        self.progress.hide()

        if state == PKG_STATE_INSTALLED:
            self.set_label(_('Installed'))
            self.set_button_label(_('Remove'))
        elif state == PKG_STATE_UNINSTALLED:
            self.set_label(view.get_price())
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UPGRADABLE:
            self.set_label(_('Upgrade Available'))
            self.set_button_label(_('Upgrade'))
        elif state == PKG_STATE_INSTALLING:
            self.set_label(_('Installing...'))
            #self.set_button_label(_('Install'))
        elif state == PKG_STATE_REMOVING:
            self.set_label(_('Removing...'))
            #self.set_button_label(_('Remove'))
        elif state == PKG_STATE_UPGRADING:
            self.set_label(_('Upgrading...'))
            #self.set_button_label(_('Upgrade Available'))
        else:
            print 'huh?'
        return

    def draw(self, cr, a, expose_area, bg_color, line_color):
        if mkit.not_overlapping(a, expose_area): return

        cr.save()
        rr = mkit.ShapeRoundedRectangle()
        rr.layout(cr,
                  a.x+1, a.y-1,
                  a.x+a.width-2, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(bg_color))
        cr.fill()

        cr.set_line_width(1)
        cr.translate(0.5, 0.5)

        rr.layout(cr,
                  a.x+1, a.y-1,
                  a.x+a.width-2, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(line_color))
        cr.stroke()

        cr.restore()
        return


class AppDescription(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self)

        self.paragraphs = []
        self.points = []
        return

    def clear(self):
        for child in self.get_children():
            self.remove(child)
            child.destroy()

        self.paragraphs = []
        self.points = []
        return

    def append_paragraph(self, fragment, newline):
        if not fragment.strip(): return
        p = gtk.Label()

        if newline:
            p.set_markup('\n'+fragment)
        else:
            p.set_markup(fragment)

        p.set_line_wrap(True)
        p.set_selectable(True)

        hb = gtk.HBox()
        hb.pack_start(p, False)

        self.pack_start(hb)
        self.paragraphs.append(p)
        return True

    def append_bullet_point(self, fragment):
        fragment = fragment.strip()
        fragment = fragment.replace('* ', '')
        fragment = fragment.replace('- ', '')

        bullet = gtk.Label()
        bullet.set_markup(u"  <big>\u2022</big>")

        a = gtk.Alignment(0.5, 0.0)
        a.add(bullet)

        point = gtk.Label()
        point.set_markup(fragment)
        point.set_line_wrap(True)
        point.set_selectable(True)

        hb = gtk.HBox(spacing=mkit.EM)
        hb.pack_start(a, False)
        hb.pack_start(point, False)

        bullet_padding = max(3, int(0.333*mkit.EM+0.5))
        a = gtk.Alignment(xscale=1.0, yscale=1.0)
        a.set_padding(bullet_padding, bullet_padding, 0, 0)
        a.add(hb)

        self.pack_start(a)
        self.points.append(point)
        return False

    def set_description(self, desc, appname):
        self.clear()

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
                    newline = self.append_paragraph(processed_desc, newline)
                else:
                    newline = self.append_bullet_point(processed_desc)

                processed_desc = ''
                processed_desc += part

                # specialcase for 7zip
                if appname == '7zip' and \
                    (i+1) < len(parts) and parts[i+1].startswith('   '): #tab
                    processed_desc += '\n'

            elif prev_part.endswith('.'):
                if in_blist:
                    in_blist = False
                    newline = self.append_bullet_point(processed_desc)
                else:
                    newline = self.append_paragraph(processed_desc, newline)

                processed_desc = ''
                processed_desc += part

            elif not prev_part.endswith(',') and part[0].isupper():
                if in_blist:
                    in_blist = False
                    newline = self.append_bullet_point(processed_desc)
                else:
                    newline = self.append_paragraph(processed_desc, newline)

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
            self.append_bullet_point(processed_desc)
        else:
            self.append_paragraph(processed_desc, newline)

        self.show_all()
        return


class PackageInfoTable(gtk.VBox):

    def __init__(self, rows=3, columns=2):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_MED)
        self.connect('realize', self._on_realize)

        self.version_label = gtk.Label()
        self.license_label = gtk.Label()
        self.support_label = gtk.Label()

        self.version_label.set_selectable(True)
        self.license_label.set_selectable(True)
        self.support_label.set_selectable(True)
        return

    def _on_realize(self, widget):
        dark = self.style.dark[self.state].to_string()
        key_markup = '<b><span color="%s">%s</span></b>'
        max_lw = 0  # max key label width

        for kstr, v in [(_('Version:'), self.version_label),
                        (_('License:'), self.license_label),
                        (_('Updates:'), self.support_label)]:
     
            k = gtk.Label()
            k.set_markup(key_markup  % (dark, kstr))
            v.set_line_wrap(True)
            max_lw = max(max_lw, k.get_layout().get_pixel_extents()[1][2])

            a = gtk.Alignment(1.0, 0.0)
            a.add(k)

            row = gtk.HBox(spacing=mkit.SPACING_XLARGE)
            row.pack_start(a, False)
            row.pack_start(v, False)
            self.pack_start(row, False)

        for row in self.get_children():
            k, v = row.get_children()
            k.set_size_request(max_lw+3*mkit.EM, -1)

        self.show_all()
        return

    def set_version(self, version):
        self.version_label.set_text(version)
        return

    def set_license(self, license):
        self.license_label.set_text(license)
        return

    def set_support_status(self, support_status):
        self.support_label.set_text(support_status)
        return



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
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

        # data
        self.pkg = None
        self.app = None
        self.iconname = ""

        # page elements are packed
        viewport = self._layout_page()

        viewport.connect('size-allocate', self._on_allocate)
        self.vbox.connect('expose-event', self._on_expose)
        return

    def _on_allocate(self, widget, allocation):
        w = allocation.width
        l = self.app_info.label.get_layout()
        if l.get_pixel_extents()[1][2] > w-48-6*mkit.EM:
            self.app_info.label.set_size_request(w-48-6*mkit.EM, -1)
        else:
            self.app_info.label.set_size_request(-1, -1)

        for p in self.app_desc.paragraphs:
            p.set_size_request(w-6*mkit.EM, -1)
        for pt in self.app_desc.points:
            pt.set_size_request(w-8*mkit.EM, -1)

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip()

        self.app_info.draw(cr, self.app_info.allocation, expose_area)
        #self.desc_section.draw(cr, self.desc_section.allocation, expose_area)

        self.action_bar.draw(cr,
                             self.action_bar.allocation,
                             event.area,
                             COLOR_GREEN_FILL,
                             COLOR_GREEN_OUTLINE)

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
        return

    def _get_pkg_state(self):
        if self.pkg:
            # Don't handle upgrades yet
            #if pkg.installed and pkg.isUpgradable:
            #    return PKG_STATE_UPGRADABLE
            if self.pkg.installed:
                return PKG_STATE_INSTALLED
            else:
                return PKG_STATE_UNINSTALLED

        elif self.doc:
            channel = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            if channel:
                #path = APP_INSTALL_CHANNELS_PATH + channel +".list"
                #if os.path.exists(path):
                    #self.channelname = channel
                    #self.channelfile = path
                    ## FIXME: deal with the EULA stuff
                    return PKG_STATE_NEEDS_SOURCE
            # check if it comes from a non-enabled component
            elif self._unavailable_component():
                # FIXME: use a proper message here, but we are in string freeze
                return PKG_STATE_UNAVAILABLE
            elif self._available_for_our_arch():
                return PKG_STATE_NEEDS_SOURCE

        return PKG_STATE_UNKNOWN

    def _layout_page(self):
        # setup widgets
        self.vbox = gtk.VBox()
        self.vbox.set_border_width(mkit.BORDER_WIDTH_LARGE)

        # we have our own viewport so we know when the viewport grows/shrinks
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.vbox)
        self.add(viewport)
        self.vbox.set_redraw_on_allocate(False)

        # framed section that contains all app details
        self.app_info = mkit.FramedSection()
        self.app_info.set_spacing(mkit.SPACING_XLARGE)
        self.app_info.header.set_spacing(mkit.SPACING_XLARGE)
        self.app_info.body.set_spacing(mkit.SPACING_XLARGE)
        self.vbox.pack_start(self.app_info, False)

        # controls which are displayed if the app is installed
        self.action_bar = PackageStatusBar(self)
        self.app_info.body.pack_start(self.action_bar, False)

        # FramedSection which contains textual paragraphs and bullet points
        self.desc_section = mkit.FramedSection(_('Description'),
                                           xpadding=mkit.SPACING_LARGE)
        self.app_info.body.pack_start(self.desc_section, False)

        # application description wigdets
        self.app_desc = AppDescription()
        self.desc_section.body.pack_start(self.app_desc, False)

        # hbox for web related links (homepage and microbloggers)
        web_hb = gtk.HBox(spacing=mkit.SPACING_MED)
        self.desc_section.body.pack_end(web_hb, False)

        # homepage link button
        self.homepage_btn = gtk.LinkButton(uri='none', label=_('Website'))
        self.homepage_btn.set_relief(gtk.RELIEF_NONE)
        web_hb.pack_start(self.homepage_btn, False)

        # share app with microbloggers button
        self.share_btn = gtk.LinkButton(uri=_('Share via micro-blogging service'),
                                        label=_('Share...'))
        self.share_btn.set_relief(gtk.RELIEF_NONE)
        self.share_btn.connect('clicked', self._on_share_clicked)
        web_hb.pack_start(self.share_btn, False)

        # package info table
        self.info_table = PackageInfoTable()
        self.app_info.body.pack_start(self.info_table, False)

        self.show_all()
        return viewport

    def _update_page(self):
        font_size = 22*pango.SCALE  # make this relative to the appicon size (48x48)
        appname = self.get_name()

        markup = '<b><span size="%s">%s</span></b>\n%s' % (font_size,
                                                           appname,
                                                           self.get_summary())

        # set app- icon, name and summary in the header
        self.app_info.set_label(markup=markup)
        self.app_info.set_icon(self.iconname or 'gnome-other',
                               gtk.ICON_SIZE_DIALOG)

        # depending on pkg install state set action labels
        self.action_bar.set_pkg_state(self._get_pkg_state())

        # format new app description
        self.app_desc.set_description(self.get_description(), appname)

        # show or hide the homepage button and set uri if homepage specified
        if self.homepage_url:
            self.homepage_btn.show()
            self.homepage_btn.set_uri(self.homepage_url)
        else:
            self.homepage_btn.hide()

        # set the strings in the package info table
        self.info_table.set_version(self.get_version_string())
        self.info_table.set_license(self.get_license())
        self.info_table.set_support_status(self.get_maintainance_time())
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

        self._update_page()
        return

    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    # substitute functions called during page display
    def get_name(self):
        return self.app.name

    def get_summary(self):
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

    def get_version_string(self):
        if not self.pkg or not self.pkg.candidate:
            return ""
        version = self.pkg.candidate.version
        if version:
            return "%s (%s)" % (version, self.pkg.name)
        return ""
    def wksub_datadir(self):
        return self.datadir
    def get_maintainance_time(self):
        """add the end of the maintainance time"""
        return self.distro.get_maintenance_status(self.cache,
            self.app.appname or self.app.pkgname, self.app.pkgname, self.component, self.channelfile)
    def wksub_action_button_description(self):
        """Add message specific to this package (e.g. how many dependenies"""
        if not self.pkg:
            return ""
        return self.distro.get_installation_status(self.cache, self.history, self.pkg, self.app.name)
    def get_license(self):
        return self.distro.get_license_text(self.component).split()[1]
    def get_price(self):
        price = self.distro.get_price(self.doc)
        #s = _("Price: %s") % price
        return price
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

    def _on_share_clicked(self, button):
        # TRANSLATORS: apturl:%(pkgname) is the apt protocol
        msg = _("Check out %(appname)s! apturl:%(pkgname)s") % {
            'appname' : self.app.appname, 
            'pkgname' : self.app.pkgname }
        p = subprocess.Popen(["gwibber-poster", "-w", "-m", msg])
        # setup timeout handler to avoid zombies
        glib.timeout_add_seconds(1, lambda p: p.poll() is None, p)
        return

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
                self.action_bar.button.set_sensitive(True)
                self.backend.emit("transaction-stopped")
                return
        self.backend.remove(self.app.pkgname, self.app.appname, self.iconname)

    def upgrade(self):
        self.backend.upgrade(self.app.pkgname, self.app.appname, self.iconname)
        return

    # internal callback
    def _on_cache_ready(self, cache):
        logging.debug("on_cache_ready")
        self.show_app(self.app)

    def _on_transaction_started(self, backend):
        self.action_bar.button.set_sensitive(False)

        state = self.action_bar.pkg_state
        if state == PKG_STATE_UNINSTALLED:
            self.action_bar.set_pkg_state(PKG_STATE_INSTALLING)
        elif state == PKG_STATE_INSTALLED:
            self.action_bar.set_pkg_state(PKG_STATE_REMOVING)
        elif state == PKG_STATE_UPGRADABLE:
            self.action_bar.set_pkg_state(PKG_STATE_UPGRADING)
        return

    def _on_transaction_stopped(self, backend):
        self.action_bar.button.set_sensitive(True)
        return

    def _on_transaction_finished(self, *args):
        self.action_bar.progress.hide()
        self.action_bar.button.show()
        self.action_bar.button.set_sensitive(True)
        return

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if not self.app or not self.app.pkgname == pkgname:
            return

        if not self.action_bar.progress.get_property('visible'):
            self.action_bar.progress.show()
            self.action_bar.button.hide()

        if pkgname in backend.pending_transactions:
            self.action_bar.progress.set_fraction(progress/100.0)
        return

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
