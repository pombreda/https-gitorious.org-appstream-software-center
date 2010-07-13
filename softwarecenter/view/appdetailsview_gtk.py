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

import dialogs
import gio
import glib
import gobject
import gtk
import logging
import os
import pango
import string
import subprocess
import sys
import xapian

from gettext import gettext as _
from softwarecenter.backend import get_install_backend
from softwarecenter.db.application import AppDetails
from softwarecenter.enums import *

from appdetailsview import AppDetailsViewBase

from widgets import mkit
from widgets.imagedialog import ShowImageDialog, GnomeProxyURLopener, Url404Error, Url403Error

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

# default socket timeout to deal with unreachable screenshot site
DEFAULT_SOCKET_TIMEOUT=4


# action colours, taken from synaptic
# reds: used for pkg_status errors or serious warnings
COLOR_RED_FILL     = '#FF9595'
COLOR_RED_OUTLINE  = '#EF2929'

# yellows: some user action is required outside of install or remove
COLOR_YELLOW_FILL    = '#FFF7B3'
COLOR_YELLOW_OUTLINE = '#FCE94F'

# greens: used for pkg installed or available for install
# and no user actions required
COLOR_GREEN_FILL    = '#D1FFA4'
COLOR_GREEN_OUTLINE = '#8AE234'

# fixed black for action bar label, taken from Ambiance gtk-theme
COLOR_BLACK         = '#323232'

class PackageStatusBar(gtk.Alignment):
    
    def __init__(self, view):
        gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)
        self.set_redraw_on_allocate(False)
        self.set_size_request(-1, int(3.5*mkit.EM+0.5))
        self.set_padding(mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL,
                         mkit.SPACING_LARGE,
                         mkit.SPACING_LARGE)

        self.hbox = gtk.HBox(spacing=mkit.SPACING_LARGE)
        self.add(self.hbox)

        self.view = view
        self.label = gtk.Label()
        self.button = gtk.Button()
        self.progress = gtk.ProgressBar()

        self.fill_color = COLOR_GREEN_FILL
        self.line_color = COLOR_GREEN_OUTLINE

        self.pkg_state = None

        self.hbox.pack_start(self.label, False)
        self.hbox.pack_end(self.button, False)
        self.hbox.pack_end(self.progress, False)
        self.show_all()

        self.button.connect('size-allocate', self._on_button_size_allocate)
        self.button.connect('clicked', self._on_button_clicked)
        return

    def _on_button_size_allocate(self, button, allocation):
        # make the progress bar the same height as the button
        self.progress.set_size_request(12*mkit.EM,
                                       allocation.height)
        return

    def _on_button_clicked(self, button):
        button.set_sensitive(False)
        state = self.pkg_state
        if state == PKG_STATE_INSTALLED:
            AppDetailsViewBase.remove(self.view)
        elif state == PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            # FIXME: implement this!
            pass
        elif state == PKG_STATE_NEEDS_PURCHASE:
            AppDetailsViewBase.buy_app(self.view)
        elif state == PKG_STATE_UNINSTALLED:
            AppDetailsViewBase.install(self.view)
        elif state == PKG_STATE_REINSTALLABLE:
            AppDetailsViewBase.install(self.view)
        elif state == PKG_STATE_UPGRADABLE:
            AppDetailsViewBase.upgrade(self.view)
        elif state == PKG_STATE_NEEDS_SOURCE:
            # FIXME:  This should be in AppDetailsViewBase
            self.view.use_this_source()
        return

    def set_label(self, label):
        m = '<b><big><span color="%s">%s</span></big></b>' % (COLOR_BLACK, label)
        self.label.set_markup(m)
        return

    def set_button_label(self, label):
        self.button.set_label(label)
        return

    def configure(self, app_details, state):
        self.pkg_state = app_details.pkg_state
        self.app_details = app_details
        self.progress.hide()

        self.fill_color = COLOR_GREEN_FILL
        self.line_color = COLOR_GREEN_OUTLINE

        # FIXME:  Use a gtk.Action for the Install/Remove/Buy/Add Source/Update Now action
        #         so that all UI controls (menu item, applist view button and appdetails
        #         view button) are managed centrally:  button text, button sensitivity,
        #         and the associated callback.
        if state == PKG_STATE_INSTALLED:
            if app_details.purchase_date:
                purchase_date = str(app_details.purchase_date).split()[0]
                self.set_label(_('Purchased on %s' % purchase_date))
            elif app_details.installation_date:
                installation_date = str(app_details.installation_date).split()[0]
                self.set_label(_('Installed on %s' % installation_date))
            else:
                self.set_label(_('Installed'))
            self.set_button_label(_('Remove'))
        elif state == PKG_STATE_NEEDS_PURCHASE:
            self.set_label(_("Buy for %s") % app_details.price)
            self.set_button_label(_('Buy'))
        elif state == PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            purchase_date = str(app_details.purchase_date).split()[0]
            self.set_label(_('Purchased on %s' % purchase_date))
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UNINSTALLED:
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_REINSTALLABLE:
            if app_details.price:
                self.set_label(app_details.price)
            self.set_button_label(_('Reinstall'))
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
        elif state == PKG_STATE_UNKNOWN:
            self.set_button_label("")
            self.set_label(_("Error"))
            self.fill_color = COLOR_RED_FILL
            self.line_color = COLOR_RED_OUTLINE
        elif state == PKG_STATE_NEEDS_SOURCE:
            channelfile = self.appdetails.channelfile
            # it has a price and is not available 
            if channelfile:
                # FIXME: deal with the EULA stuff
                self.set_button_label(_("Use This Source"))
            # check if it comes from a non-enabled component
            elif self.appdetails._unavailable_component():
                # FIXME: use a proper message here, but we are in string freeze
                self.set_button_label(_("Use This Source"))
            elif self.appdetails._available_for_our_arch():
                self.set_button_label(_("Update Now"))
            self.fill_color = COLOR_YELLOW_FILL
            self.line_color = COLOR_YELLOW_OUTLINE
        return

    def draw(self, cr, a, expose_area):
        if mkit.not_overlapping(a, expose_area): return

        cr.save()
        rr = mkit.ShapeRoundedRectangle()
        rr.layout(cr,
                  a.x+1, a.y-1,
                  a.x+a.width-2, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(self.fill_color))
        cr.fill()

        cr.set_line_width(1)
        cr.translate(0.5, 0.5)

        rr.layout(cr,
                  a.x+1, a.y-1,
                  a.x+a.width-2, a.y+a.height,
                  radius=mkit.CORNER_RADIUS)

        cr.set_source_rgb(*mkit.floats_from_string(self.line_color))
        cr.stroke()
        cr.restore()
        return


class AppDescription(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_LARGE)
        self.body = gtk.VBox()
        self.footer = gtk.HBox(spacing=mkit.SPACING_MED)

        self.pack_start(self.body, False)
        self.pack_start(self.footer, False)
        self.show_all()

        self._newline = False
        self.paragraphs = []
        self.points = []
        return

    def clear(self):
        for child in self.body.get_children():
            self.body.remove(child)
            child.destroy()

        self.paragraphs = []
        self.points = []
        return

    def append_paragraph(self, fragment):
        p = gtk.Label()
        p.set_markup(fragment)
        p.set_line_wrap(True)
        p.set_selectable(True)

        hb = gtk.HBox()
        hb.pack_start(p, False)

        self.body.pack_start(hb, False)
        self.paragraphs.append(p)
        return

    def append_bullet_point(self, fragment):
        fragment = fragment.replace('* ', '')
        fragment = fragment.replace('- ', '')

        bullet = gtk.Label()
        bullet.set_markup(u"  <b>\u2022</b>")

        a = gtk.Alignment(0.5, 0.0)
        a.add(bullet)

        point = gtk.Label()
        point.set_markup(fragment)
        point.set_line_wrap(True)
        point.set_selectable(True)

        hb = gtk.HBox(spacing=mkit.EM)
        hb.pack_start(a, False)
        hb.pack_start(point, False)

        a = gtk.Alignment(xscale=1.0, yscale=1.0)
        a.set_padding(4,4,0,0)
        a.add(hb)

        self.body.pack_start(a, False)
        self.points.append(point)
        return

    def set_description(self, desc, appname):
        """ Attempt to maintain original fixed width layout, while 
            reconstructing the description into text blocks (either paragraphs or
            bullets) which are line-wrap friendly.
        """

        #print desc
        self.clear()
        desc = gobject.markup_escape_text(desc)

        parts = desc.split('\n')
        l = len(parts)

        in_blist = False
        processed_frag = ''

        for i, part in enumerate(parts):
            part = part.strip()

            # if empty, do the void
            if not part:
                pass

            else:
                # frag looks like its a bullet point
                if part[:2] in ('- ', '* '):
                    # if there's an existing bullet, append it and start anew
                    if in_blist:
                        self.append_bullet_point(processed_frag)
                        processed_frag = ''

                    in_blist = True

                processed_frag += part

                # ends with a terminator or the following fragment starts with a capital letter
                if part[-1] in ('.', '!', '?', ':') or \
                    (i+1 < l and len(parts[i+1]) > 1 and \
                        parts[i+1][0].isupper()):

                    # not in a bullet list, so normal paragraph
                    if not in_blist:
                        # if not final text block, append newline
                        if (i+1) < l:
                            processed_frag += '\n'
                        # append text block
                        self.append_paragraph(processed_frag)
                        # reset
                        processed_frag = ''

                    # we are in a bullet list
                    else:
                        # append newline only if this is not the final
                        # text block and its not followed by a bullet 
                        if (i+1) < l and len(parts[i+1]) > 1 and not \
                            parts[i+1][:2] in ('- ', '* '):
                            processed_frag += '\n'

                        # append a bullet point
                        self.append_bullet_point(processed_frag)
                        # reset
                        processed_frag = ''
                        in_blist = False

                else:
                    processed_frag += ' '

        if processed_frag:
            if processed_frag[:2] in ('- ', '* '):
                self.append_bullet_point(processed_frag)
            else:
                self.append_paragraph(processed_frag)

        self.show_all()
        return    


class PackageInfoTable(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_MED)

        self.version_label = gtk.Label()
        self.license_label = gtk.Label()
        self.support_label = gtk.Label()

        self.version_label.set_selectable(True)
        self.license_label.set_selectable(True)
        self.support_label.set_selectable(True)

        self.connect('realize', self._on_realize)
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

    def set_width(self, width):
        for row in self.get_children():
            k, v = row.get_children()
            v.set_size_request(width-k.allocation.width-row.get_spacing(), -1)
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


class ScreenshotDownloader(gobject.GObject):

    __gsignals__ = {
        "url-reachable"     : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               (bool,),),

        "download-complete" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               (str,),),
        }


    def __init__(self):
        gobject.GObject.__init__(self)
        return

    def _actually_download_screenshot(self, file, url):

        def download_complete_cb(file, result, path="/tmp/SoftwareCenterScreenshot.png"):
            """Helper called after the file has downloaded"""

            # The result from the download is actually a tuple with three elements.
            # The first element is the actual content so let's grab that
            content = file.load_contents_finish(result)[0]

            # let's now save the content to the tmp dir
            outputfile = open(path, "w")
            outputfile.write(content)

            self.emit('download-complete', path)
            return

        file.load_contents_async(download_complete_cb)
        return

    def download_from_url(self, url):

        def query_complete_cb(file, result):
            try:
                result = file.query_info_finish(result)
                self.emit('url-reachable', True)
                self._actually_download_screenshot(file, url)
            except glib.GError, e:
                self.emit('url-reachable', False)

            del file
            return

        # use gio (its so nice)
        file=gio.File(url)
        file.query_info_async(gio.FILE_ATTRIBUTE_STANDARD_SIZE,
                              query_complete_cb)
        return

gobject.type_register(ScreenshotDownloader)


class ScreenshotView(gtk.Alignment):

    def __init__(self, distro, icons):
        gtk.Alignment.__init__(self, 0.5, 0.0)
        self.set_redraw_on_allocate(False)
        self.set_border_width(3)

        event = gtk.EventBox()
        event.set_visible_window(False)
        self.add(event)
        self.image = gtk.Image()
        self.image.set_redraw_on_allocate(False)
        event.add(self.image)
        self.eventbox = event
        self.image.connect('expose-event', self._on_image_expose)

        # unavailable layout
        l = gtk.Label(_('No screenshot'))
        l.set_state(gtk.STATE_INSENSITIVE)
        self.unavailable = gtk.Alignment(0.5, 0.5)
        self.unavailable.add(l)

        self.set_flags(gtk.CAN_FOCUS)
        event.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                         gtk.gdk.BUTTON_RELEASE_MASK|
                         gtk.gdk.KEY_RELEASE_MASK|
                         gtk.gdk.KEY_PRESS_MASK|
                         gtk.gdk.ENTER_NOTIFY_MASK|
                         gtk.gdk.LEAVE_NOTIFY_MASK)

        event.connect('enter-notify-event', self._on_enter)
        event.connect('leave-notify-event', self._on_leave)
        event.connect('button-press-event', self._on_press)
        event.connect('button-release-event', self._on_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)

        self.distro = distro
        self.icons = icons

        self.appname = None
        self.thumb_url = None
        self.large_url = None

        self.ready = False
        self.screenshot_available = False
        self.alpha = 0.0

        self.loader = ScreenshotDownloader()
        self.loader.connect('url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('download-complete', self._on_screenshot_download_complete)
        return

    def _on_enter(self, widget, event):
        if self.get_is_actionable():
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        return

    def _on_leave(self, widget, event):
        self.window.set_cursor(None)
        return

    def _on_press(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_release(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(gtk.STATE_NORMAL)
        self._show_image_dialog()
        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421) and self.get_is_actionable():
            self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421) and self.get_is_actionable():
            self.set_state(gtk.STATE_NORMAL)
            self._show_image_dialog()
        return

    def _on_image_expose(self, widget, event):
        if widget.get_storage_type() != gtk.IMAGE_PIXBUF:
            return

        pb = widget.get_pixbuf()
        if not pb: return True

        a = widget.allocation
        cr = widget.window.cairo_create()

        cr.rectangle(a)
        cr.clip()

        cr.set_source_pixbuf(pb, a.x, a.y)
        cr.paint_with_alpha(self.alpha)
        return True

    def _fade_in(self):
        self.alpha += 0.05
        if self.alpha >= 1.0:
            self.alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _show_image_dialog(self):
        url = self.large_url
        title = _("%s - Screenshot") % self.appname
        d = ShowImageDialog(
            title, url,
            self.icons.lookup_icon("process-working", 32, ()).get_filename(),
            self.icons.lookup_icon("process-working", 32, ()).get_base_size(),
            self.distro.IMAGE_FULL_MISSING)

        d.run()
        d.destroy()
        return

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable: self.ready = True
        return

    def _on_screenshot_download_complete(self, loader, screenshot_path):

        def setter_cb(path):
            self.image.set_size_request(-1, -1)
            pb = gtk.gdk.pixbuf_new_from_file(path)
            self.image.set_from_pixbuf(pb)
            gobject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        gobject.idle_add(setter_cb, screenshot_path)
        return

    def get_is_actionable(self):
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):
        if not available:
            if self.image.parent:
                self.eventbox.remove(self.image)
                self.eventbox.add(self.unavailable)
                self.unavailable.set_size_request(160, 100)
                self.unavailable.show_all()
                acc = self.get_accessible()
                acc.set_name(_('%s - No screenshot available' % self.appname))
        else:
            if self.unavailable.parent:
                self.eventbox.remove(self.unavailable)
                self.eventbox.add(self.image)
                self.image.show()
                acc = self.get_accessible()
                acc.set_name(_('%s - Screenshot' % self.appname))

        self.screenshot_available = available
        return
 
    def configure(self, app_details):
        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))

        self.clear()
        self.appname = app_details.name
        self.thumbnail_url = app_details.thumbnail
        self.large_url = app_details.screenshot
        return

    def clear(self):
        self.screenshot_available = True
        self.ready = False
        self.alpha = 0.0

        if self.unavailable.parent:
            self.eventbox.remove(self.unavailable)
            self.eventbox.add(self.image)
            self.image.show()

        self.image.set_from_file(AppDetailsViewGtk.IMAGE_LOADING_INSTALLED)
        self.image.set_size_request(160, 100)
        return

    def download_and_display(self):
        self.loader.download_from_url(self.thumbnail_url)
        return

    def draw(self, cr, a, expose_area):
        if mkit.not_overlapping(a, expose_area): return

        if self.image.parent:
            ia = self.image.allocation
        else:
            ia = self.unavailable.allocation

        x = a.x + (a.width - ia.width)/2
        y = ia.y

        if self.has_focus() or self.state == gtk.STATE_ACTIVE:
            cr.rectangle(x-2, y-2, ia.width+4, ia.height+4)
            cr.set_source_rgb(1,1,1)
            cr.fill_preserve()
            if self.state == gtk.STATE_ACTIVE:
                color = mkit.floats_from_gdkcolor(self.style.mid[self.state])
            else:
                color = mkit.floats_from_gdkcolor(self.style.dark[gtk.STATE_SELECTED])
            cr.set_source_rgb(*color)
            cr.stroke()
        else:
            cr.rectangle(x-3, y-3, ia.width+6, ia.height+6)
            cr.set_source_rgb(1,1,1)
            cr.fill()
            cr.save()
            cr.translate(0.5, 0.5)
            cr.set_line_width(1)
            cr.rectangle(x-3, y-3, ia.width+5, ia.height+5)

            dark = mkit.floats_from_gdkcolor(self.style.dark[self.state])
            cr.set_source_rgb(*dark)
            cr.stroke()
            cr.restore()

        if not self.screenshot_available:
            cr.rectangle(x, y, ia.width, ia.height)
            cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.bg[self.state]))
            cr.fill()
        return


class AppDetailsViewGtk(gtk.Viewport, AppDetailsViewBase):

    """ The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = gtk.ICON_SIZE_DIALOG

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
                    }


    def __init__(self, db, distro, icons, cache, history, datadir):
        gtk.Viewport.__init__(self)
        AppDetailsViewBase.__init__(self, db, distro, icons, cache, history, datadir)
        self.set_shadow_type(gtk.SHADOW_NONE)

        # atk
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Description"))

        # aptdaemon
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

        # app specific data
        self.app = None
        self.app_details = None

        self.gwibber_is_available = os.path.exists("/usr/bin/gwibber-poster")

        # page elements are packed into our very own lovely viewport
        self._layout_page()
        self.connect('size-allocate', self._on_allocate)
        self.vbox.connect('expose-event', self._on_expose)
        return

    def _on_allocate(self, widget, allocation):
        w = allocation.width
        magic_number = 6*mkit.EM    # !?
        l = self.app_info.label.get_layout()
        if l.get_pixel_extents()[1][2] > w-48-7*mkit.EM:
            self.app_info.label.set_size_request(w-48-7*mkit.EM, -1)
        else:
            self.app_info.label.set_size_request(-1, -1)

        for p in self.app_desc.paragraphs:
            p.set_size_request(w-7*mkit.EM-166, -1)
            
        for pt in self.app_desc.points:
            pt.set_size_request(w-9*mkit.EM-166, -1)

        self.info_table.set_width(w-magic_number)

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip()

        self.app_info.draw(cr, self.app_info.allocation, expose_area)

        self.action_bar.draw(cr,
                             self.action_bar.allocation,
                             event.area)

        self.screenshot.draw(cr, self.screenshot.allocation, expose_area)
        del cr
        return

    def _on_share_clicked(self, button):
        # TRANSLATORS: apturl:%(pkgname) is the apt protocol
        msg = _("Check out %(appname)s! apturl:%(pkgname)s") % {
            'appname' : self.app_details.name, 
            'pkgname' : self.app_details.pkgname }
        p = subprocess.Popen(["gwibber-poster", "-w", "-m", msg])
        # setup timeout handler to avoid zombies
        glib.timeout_add_seconds(1, lambda p: p.poll() is None, p)
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

    def _layout_page(self):
        # setup widgets

        # root vbox
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.vbox.set_border_width(mkit.BORDER_WIDTH_LARGE)

        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox.set_redraw_on_allocate(False)

        # framed section that contains all app details
        self.app_info = mkit.FramedSection()
        self.app_info.set_spacing(mkit.SPACING_XLARGE)
        self.app_info.header.set_spacing(mkit.SPACING_XLARGE)
        self.app_info.header_alignment.set_padding(mkit.SPACING_XLARGE,
                                                   mkit.SPACING_LARGE,
                                                   mkit.SPACING_XLARGE,
                                                   mkit.SPACING_XLARGE)

        self.app_info.body.set_spacing(mkit.SPACING_XLARGE)
        self.vbox.pack_start(self.app_info, False)

        # controls which are displayed if the app is installed
        self.action_bar = PackageStatusBar(self)
        self.app_info.body.pack_start(self.action_bar, False)

        # FramedSection which contains textual paragraphs and bullet points
        self.desc_section = mkit.FramedSection(_('Description'),
                                               xpadding=mkit.SPACING_LARGE)
        self.app_info.body.pack_start(self.desc_section, False)

        app_desc_hb = gtk.HBox(spacing=mkit.SPACING_LARGE)
        self.desc_section.body.pack_start(app_desc_hb)

        # application description wigdets
        self.app_desc = AppDescription()
        app_desc_hb.pack_start(self.app_desc, False)

        # screenshot
        self.screenshot = ScreenshotView(self.distro, self.icons)
        app_desc_hb.pack_end(self.screenshot)

        # homepage link button
        self.homepage_btn = gtk.LinkButton(uri='none', label=_('Website'))
        self.homepage_btn.set_relief(gtk.RELIEF_NONE)
        self.app_desc.footer.pack_start(self.homepage_btn, False)

        # share app with microbloggers button
        self.share_btn = gtk.LinkButton(uri=_('Share via micro-blogging service'),
                                        label=_('Share...'))

        self.share_btn.set_relief(gtk.RELIEF_NONE)
        self.share_btn.connect('clicked', self._on_share_clicked)
        self.app_desc.footer.pack_start(self.share_btn, False)

        # package info table
        self.info_table = PackageInfoTable()
        self.app_info.body.pack_start(self.info_table, False)

        self.show_all()
        return

    def _update_page(self, app_details):
        # FIXME: check if we actually need that argument up there..
        self.app_details = app_details

        # make title font size fixed as they should look good compared to the 
        # icon (also fixed).
        big = 20*pango.SCALE
        small = 9*pango.SCALE
        appname = gobject.markup_escape_text(self.app_details.name)

        markup = '<b><span size="%s">%s</span></b>\n<span size="%s">%s</span>'
        # FIXME: Once again (yes, I am working from the end to the beginning of the file..) this is tmp until we find a better place for the errors
        if self.app_details.error:
            summary = self.app_details.error
        else:
            summary = self.app_details.summary
        markup = markup % (big, appname, small, gobject.markup_escape_text(summary))

        # set app- icon, name and summary in the header
        self.app_info.set_label(markup=markup)
        icon = None
        if self.app_details.icon:
            if self.icons.has_icon(self.app_details.icon):
                icon = self.app_details.icon
        if not icon:
            icon = MISSING_APP_ICON
        self.app_info.set_icon(icon, gtk.ICON_SIZE_DIALOG)

        # depending on pkg install state set action labels
        self.action_bar.configure(self.app_details, self.app_details.pkg_state)

        self.action_bar.button.grab_focus()

        # format new app description
        # FIXME: This is a bit messy, but the warnings need to be displayed somewhere until we find a better place for them
        # IDEA:  Put warning into the PackageStatusBar.  Makes sense(?).
        if self.app_details.warning:
            if self.app_details.description:
                description = "Warning: " + self.app_details.warning + "\n\n" + self.app_details.description
            else:
                description = "Warning: " + self.app_details.warning
        else:
            description = self.app_details.description
        if description:
            self.app_desc.set_description(description, appname)

        # show or hide the homepage button and set uri if homepage specified
        if self.app_details.website:
            self.homepage_btn.show()
            self.homepage_btn.set_property('visited', False)
            self.homepage_btn.set_uri(self.app_details.website)
        else:
            self.homepage_btn.hide()

        # check if gwibber-poster is available, if so display Share... btn
        if self.gwibber_is_available and not self.app_details.error:
            self.share_btn.show()
            self.share_btn.set_property('visited', False)
        else:
            self.share_btn.hide()

        # get screenshot urls and configure the ScreenshotView...
        if self.app_details.thumbnail and self.app_details.screenshot:
            self.screenshot.configure(self.app_details)

            # then begin screenshot download and display sequence
            self.screenshot.download_and_display()

        # set the strings in the package info table
        if self.app_details.version:
            self.info_table.set_version(self.app_details.version + "(" + self.app_details.pkgname + ")")
        else:
            self.info_table.set_version(_("Unknown"))
        if self.app_details.license:
            self.info_table.set_license(self.app_details.license)
        else:
            self.info_table.set_license(_("Unknown"))
        if self.app_details.maintenance_status:
            self.info_table.set_support_status(self.app_details.maintenance_status)
        else:
            self.info_table.set_support_status(_("Unknown"))
        return

    # public API
    # FIXME:  port to AppDetailsViewBase as
    #         AppDetailsViewBase.show_app(self, app)
    def show_app(self, app):
        logging.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            return
        
        # set button sensitive again
        self.action_bar.button.set_sensitive(True)

        # init data
        self.app = app
        self.app_details = app.get_details(self.db)
        # for compat with the base class
        self.appdetails = self.app_details
        #print "AppDetailsViewGtk:"
        #print self.appdetails
        # self.emit("selected", self.app)  # << redundant??
        self._update_page(self.app_details)
        self.emit("selected", self.app)
        return

    # public interface
    def use_this_source(self):
        if self.app_details.channelfile:
            self.backend.enable_channel(self.app_details.channelfile)
        elif self.app_details.component:
            # this is broken atm?
            self.backend.enable_component(self.app_details.component)

    # internal callback
    def _update_interface_on_trans_ended(self):
        self.action_bar.button.set_sensitive(True)
        self.action_bar.button.show()

        state = self.action_bar.pkg_state
        if state == PKG_STATE_REMOVING:
            self.action_bar.configure(self.app_details, PKG_STATE_UNINSTALLED)
        elif state == PKG_STATE_INSTALLING:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLED)
        elif state == PKG_STATE_UPGRADING:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLED)
        return False

    def _on_transaction_started(self, backend):
        self.action_bar.button.hide()
        state = self.action_bar.pkg_state
        if state == PKG_STATE_UNINSTALLED:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLING)
        elif state == PKG_STATE_INSTALLED:
            self.action_bar.configure(self.app_details, PKG_STATE_REMOVING)
        elif state == PKG_STATE_UPGRADABLE:
            self.action_bar.configure(self.app_details, PKG_STATE_UPGRADING)
        return

    def _on_transaction_stopped(self, backend):
        self.action_bar.progress.hide()
        self._update_interface_on_trans_ended()
        return

    def _on_transaction_finished(self, backend, success):
        self.action_bar.progress.hide()
        self._update_interface_on_trans_ended()
        return

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if self.app_details and self.app_details.pkgname and self.app_details.pkgname == pkgname:
            if not self.action_bar.progress.get_property('visible'):
                gobject.idle_add(self._show_prog_idle_cb)
            if pkgname in backend.pending_transactions:
                self.action_bar.progress.set_fraction(progress/100.0)
        return

    def _show_prog_idle_cb(self):
        # without using an idle callback, the progressbar suffers from
        # gitter as it gets allocated on show().  This approach either eliminates
        # the issue or makes it unnoticeable... 
        self.action_bar.progress.show()
        return False

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

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    from softwarecenter.apt.apthistory import get_apt_history
    history = get_apt_history()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsViewGtk(db, distro, icons, cache, history, datadir)
    from softwarecenter.db.application import Application
    view.show_app(Application("Pay App Example", "pay-app"))
    #view.show_app(Application("3D Chess", "3dchess"))
    #view.show_app(Application("Movie Player", "totem"))
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
