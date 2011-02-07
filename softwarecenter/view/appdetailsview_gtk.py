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

import atk
import gettext
import glib
import gmenu
import gobject
import gtk
import logging
import os
import pango
import subprocess
import sys
import cairo

from softwarecenter.netstatus import NetState, get_network_state, get_network_watcher

from PIL import Image
from gettext import gettext as _
import apt_pkg
from softwarecenter.db.application import Application
from softwarecenter.db.reviews import ReviewStats
from softwarecenter.backend.zeitgeist_simple import zeitgeist_singleton
from softwarecenter.enums import *
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR
from softwarecenter.utils import ImageDownloader, GMenuSearcher, uri_to_filename, is_unity_running, upstream_version_compare, upstream_version
from softwarecenter.gwibber_helper import GWIBBER_SERVICE_AVAILABLE

from appdetailsview import AppDetailsViewBase

from widgets import mkit
from widgets.mkit import EM
from widgets.label import IndentLabel
from widgets.imagedialog import ShowImageDialog

from widgets.reviews import ReviewStatsContainer, StarRating

from softwarecenter.backend.config import get_config

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

# fixed black for action bar label, taken from Ambiance gtk-theme
COLOR_BLACK         = '#323232'

LOG = logging.getLogger("softwarecenter.view.appdetailsview")


class StatusBar(gtk.Alignment):
    
    def __init__(self, view):
        gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)
        self.set_redraw_on_allocate(False)
        self.set_padding(mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL+2,
                         mkit.SPACING_SMALL)

        self.hbox = gtk.HBox(spacing=mkit.SPACING_SMALL)
        self.add(self.hbox)

        self.view = view

        self._height = 1

        self.connect('size-allocate', self._on_size_allocate)
        self.connect('style-set', self._on_style_set)
        
    def _on_size_allocate(self, button, allocation):
        # Bug #617443
        # Dont allow the package status bar to shrink
        self._height = max(allocation.height, self._height)
        if allocation.height < self._height:
            self.set_size_request(-1, self._height)
        return

    def _on_style_set(self, widget, old_style):
        # reset max heights, this is so we can resize properly on, say, a font-size change
        self._height = 1
        self.set_size_request(-1, -1)
        return
        
    def draw(self, cr, a, expose_area):
        if mkit.not_overlapping(a, expose_area): return

        cr.save()
        if self.view.section:
            r,g,b = self.view.section._section_color
        else:
            r,g,b = 0.5,0.5,0.5

        cr.rectangle(a)
        cr.set_source_rgba(r,g,b,0.333)
#        cr.set_source_rgb(*mkit.floats_from_string(self.line_color))
        cr.fill()

        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        cr.rectangle(a.x, a.y, a.width-1, a.height-1)
        cr.set_source_rgba(r,g,b,0.5)
        cr.stroke()
        cr.restore()
        return


class PackageStatusBar(StatusBar):
    
    def __init__(self, view):
        StatusBar.__init__(self, view)
        self.label = mkit.EtchedLabel()
        self.button = gtk.Button()
        self.progress = gtk.ProgressBar()

        self.pkg_state = None

        self.hbox.pack_start(self.label, False)
        self.hbox.pack_end(self.button, False)
        self.hbox.pack_end(self.progress, False)
        self.show_all()

        self.button.connect('clicked', self._on_button_clicked)
        glib.timeout_add(500, self._pulse_helper)

    def _pulse_helper(self):
        if (self.pkg_state == PKG_STATE_INSTALLING_PURCHASED and
            self.progress.get_fraction() == 0.0):
            self.progress.pulse()
        return True

    def _on_button_clicked(self, button):
        button.set_sensitive(False)
        state = self.pkg_state
        self.view.addons_to_install = self.view.addons_manager.addons_to_install
        self.view.addons_to_remove = self.view.addons_manager.addons_to_remove
        if state == PKG_STATE_INSTALLED:
            AppDetailsViewBase.remove(self.view)
        elif state == PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            AppDetailsViewBase.reinstall_purchased(self.view)
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
        m = '<span color="%s">%s</span>' % (COLOR_BLACK, label)
        self.label.set_markup(m)
        return

    def set_button_label(self, label):
        self.button.set_label(label)
        return

    def configure(self, app_details, state):
        LOG.debug("configure %s state=%s pkgstate=%s" % (
                app_details.pkgname, state, app_details.pkg_state))
        self.pkg_state = state
        self.app_details = app_details

        #~ self.fill_color = COLOR_BLACK
        #~ self.line_color = COLOR_GREEN_OUTLINE

        if state in (PKG_STATE_INSTALLING,
                     PKG_STATE_INSTALLING_PURCHASED,
                     PKG_STATE_REMOVING,
                     PKG_STATE_UPGRADING,
                     APP_ACTION_APPLY):
            self.show()
        elif state == PKG_STATE_NOT_FOUND:
            self.hide()
        elif state == PKG_STATE_ERROR:
            self.button.set_sensitive(False)
            self.button.show()
            self.show()
        else:
            state = app_details.pkg_state
            self.pkg_state = state
            self.button.set_sensitive(True)
            self.button.show()
            self.show()
            self.progress.hide()

        # FIXME:  Use a gtk.Action for the Install/Remove/Buy/Add Source/Update Now action
        #         so that all UI controls (menu item, applist view button and appdetails
        #         view button) are managed centrally:  button text, button sensitivity,
        #         and the associated callback.
        if state == PKG_STATE_INSTALLING:
            self.set_label(_('Installing...'))
            self.button.set_sensitive(False)
        elif state == PKG_STATE_INSTALLING_PURCHASED:
            self.set_label(_(u'Installing purchase\u2026'))
            self.button.hide()
            self.progress.show()
        elif state == PKG_STATE_REMOVING:
            self.set_label(_('Removing...'))
            self.button.set_sensitive(False)
        elif state == PKG_STATE_UPGRADING:
            self.set_label(_('Upgrading...'))
            self.button.set_sensitive(False)
        elif state == PKG_STATE_INSTALLED or state == PKG_STATE_REINSTALLABLE:
            if app_details.purchase_date:
                purchase_date = str(app_details.purchase_date).split()[0]
                self.set_label(_('Purchased on %s') % purchase_date)
            elif app_details.installation_date:
                installation_date = str(app_details.installation_date).split()[0]
                self.set_label(_('Installed on %s') % installation_date)
            else:
                self.set_label(_('Installed'))
            if state == PKG_STATE_REINSTALLABLE: # only deb files atm
                self.set_button_label(_('Reinstall'))
            elif state == PKG_STATE_INSTALLED:
                self.set_button_label(_('Remove'))
        elif state == PKG_STATE_NEEDS_PURCHASE:
            # FIXME:  need to determine the currency dynamically once we can
            #         get that info from the software-center-agent/payments service.
            # NOTE:  the currency string for this label is purposely not translatable
            #        when hardcoded, since it (currently) won't vary based on locale
            #        and as such we don't want it translated
            self.set_label("US$ %s" % app_details.price)
            self.set_button_label(_(u'Buy\u2026'))
        elif state == PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            purchase_date = str(app_details.purchase_date).split()[0]
            self.set_label(_('Purchased on %s') % purchase_date)
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UNINSTALLED:
            if app_details.price:
                self.set_label(app_details.price)
            else:
                self.set_label(_("Free"))
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UPGRADABLE:
            self.set_label(_('Upgrade Available'))
            self.set_button_label(_('Upgrade'))
        elif state == APP_ACTION_APPLY:
            self.set_label(_(u'Changing Add-ons\u2026'))
            self.button.set_sensitive(False)
        elif state == PKG_STATE_UNKNOWN:
            self.set_button_label("")
            self.set_label(_("Error"))
        elif state == PKG_STATE_ERROR:
            # this is used when the pkg can not be installed
            # we display the error in the description field
            self.set_button_label(_("Install"))
            self.set_label("")
            self.fill_color = COLOR_RED_FILL
            self.line_color = COLOR_RED_OUTLINE
        elif state == PKG_STATE_NOT_FOUND:
            # this is used when the pkg is not in the cache and there is no request
            # we display the error in the summary field and hide the rest
            pass
        elif state == PKG_STATE_NEEDS_SOURCE:
            channelfile = self.app_details.channelfile
            # it has a price and is not available 
            if channelfile:
                self.set_button_label(_("Use This Source"))
            # check if it comes from a non-enabled component
            elif self.app_details._unavailable_component():
                self.set_button_label(_("Use This Source"))
            else:
                # FIXME: This will currently not be displayed,
                #        because we don't differenciate between
                #        components that are not enabled or that just
                #        lack the "Packages" files (but are in sources.list)
                self.set_button_label(_("Update Now"))
            self.fill_color = COLOR_YELLOW_FILL
            self.line_color = COLOR_YELLOW_OUTLINE
        if (self.app_details.warning and not self.app_details.error and
           not state in (PKG_STATE_INSTALLING, PKG_STATE_INSTALLING_PURCHASED,
           PKG_STATE_REMOVING, PKG_STATE_UPGRADING, APP_ACTION_APPLY)):
            self.set_label(self.app_details.warning)
        return


class AppDescription(gtk.VBox):

    # chars that server as bullets in the description
    BULLETS = ('- ', '* ', 'o ')
    TYPE_PARAGRAPH = 0
    TYPE_BULLET    = 1

    def __init__(self):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_LARGE)
        self.set_resize_mode(gtk.RESIZE_IMMEDIATE)

        self.description = IndentLabel()
        self.footer = gtk.HBox(spacing=mkit.SPACING_MED)

        self.pack_start(self.description, False)
        self.pack_start(self.footer, False)
        self.show_all()

        self._prev_type = None
        return

    def clear(self):
        self.description.clear()
        return

    def append_paragraph(self, p):
        self.description.append_paragraph(p.strip())
        self._prev_type = self.TYPE_PARAGRAPH
        return

    def append_bullet(self, point, indent_level):
        vspacing=None
        if self._prev_type == self.TYPE_BULLET:
            vspacing = 5

        self.description.append_bullet(point[2:].strip(),
                                       indent_level+1,
                                       vspacing)
        self._prev_type = self.TYPE_BULLET
        return

    def set_description(self, desc, appname):
        """ Attempt to maintain original fixed width layout, while 
            reconstructing the description into text blocks 
            (either paragraphs or bullets) which are line-wrap friendly.
        """

        LOG.debug("description: '%s' " % desc)
        self.clear()
        desc = gobject.markup_escape_text(desc)

        parts = desc.split('\n')
        l = len(parts)

        in_blist = False
        processed_frag = ''
        prev_indent = 0
        indent = 0

        for i, raw_part in enumerate(parts):
            part = raw_part.strip()
            #indent = 0#len(raw_part) - len(part)
#            print len(raw_part) - len(part), part

            if not part:
                # if empty, do the void
                continue

            # frag looks like its a bullet point
            if part[:2] in self.BULLETS:
                # if there's an existing bullet, append it and start anew
                if in_blist:
                    self.append_bullet(processed_frag, prev_indent)
                    processed_frag = ''

                in_blist = True

            processed_frag += part

            # ends with a terminator or the following fragment starts with a capital letter
            if (part[-1] in ('.', '!', '?', ':') or
               (i+1 < l and len(parts[i+1]) > 1 and parts[i+1][0].isupper()) or
               (i+1 < l and parts[i+1] == '')):
                # not in a bullet list, so normal paragraph
                if not in_blist:
                    # if not final text block, append newline
                    # append text block
                    self.append_paragraph(processed_frag)
                    # reset
                    processed_frag = ''

                # we are in a bullet list
                else:
                    # append a bullet point
                    self.append_bullet(processed_frag, indent)
                    # reset
                    processed_frag = ''
                    in_blist = False

            else:
                processed_frag += ' '

            #prev_indent = indent

        if processed_frag:
            if processed_frag[:2] in self.BULLETS:
                self.append_bullet(processed_frag, indent)
            else:
                self.append_paragraph(processed_frag)

        return


class PackageInfo(gtk.HBox):

    def __init__(self, key, info_keys):
        gtk.HBox.__init__(self, spacing=mkit.SPACING_XLARGE)
        self.key = key
        self.info_keys = info_keys
        self.info_keys.append(key)
        self.value_label = gtk.Label()
        self.value_label.set_selectable(True)
        self.a11y = self.get_accessible()
        self.connect('realize', self._on_realize)
        return

    def _on_realize(self, widget):
        # key
        k = gtk.Label()
        dark = self.style.dark[self.state].to_string()
        key_markup = '<b><span color="%s">%s</span></b>'
        k.set_markup(key_markup  % (dark, self.key))
        a = gtk.Alignment(1.0, 0.0)
        # determine max width of all keys
        max_lw = 0
        for key in self.info_keys:
            tmp = gtk.Label()
            tmp.set_markup(key_markup  % (dark, key))
            max_lw = max(max_lw, tmp.get_layout().get_pixel_extents()[1][2])
            del tmp

        a.set_size_request(max_lw+3*EM, -1)
        a.add(k)
        self.pack_start(a, False)

        # value
        v = self.value_label
        v.set_line_wrap(True)
        v.set_selectable(True)
        b = gtk.Alignment(0.0, 0.0)
        b.add(v)
        self.pack_start(b, False)

        # a11y
        kacc = k.get_accessible()
        vacc = v.get_accessible()
        kacc.add_relationship(atk.RELATION_LABEL_FOR, vacc)
        vacc.add_relationship(atk.RELATION_LABELLED_BY, kacc)

        self.set_property("can-focus", True)

        self.show_all()
        return

    def set_width(self, width):
        if self.get_children():
            k, v = self.get_children()
            l = v.get_children()[0]
            l.set_size_request(width-k.allocation.width-self.get_spacing(), -1)
        return

    def set_value(self, value):
        self.value_label.set_markup(value)
        self.a11y.set_name(self.key + ' ' + self.value_label.get_text())


class ScreenshotView(gtk.Alignment):

    """ Widget that displays screenshot availability, download prrogress,
        and eventually the screenshot itself.
    """

    def __init__(self, distro, icons):
        # center child widgets in the available horizontal space (0.5)
        # 0.0 == left/top margin, 0.5 == center, 1.0 == right/bottom margin
        gtk.Alignment.__init__(self, 0.5, 0.0)
        self.set_redraw_on_allocate(False)

        # the frame around the screenshot (placeholder)
        self.set_border_width(3)

        # eventbox so we can connect to event signals
        event = gtk.EventBox()
        event.set_visible_window(False)
        self.add(event)

        # the image
        self.image = gtk.Image()
        self.image.set_redraw_on_allocate(False)
        event.add(self.image)
        self.eventbox = event

        # connect the image to our custom draw func for fading in
        self.image.connect('expose-event', self._on_image_expose)

        # unavailable layout
        l = gtk.Label(_('No screenshot'))
        # force the label state to INSENSITIVE so we get the nice subtle etched in look
        l.set_state(gtk.STATE_INSENSITIVE)
        # center children both horizontally and vertically
        # 0.0 == left/top margin, 0.5 == center, 1.0 == right/bottom margin
        self.unavailable = gtk.Alignment(0.5, 0.5)
        self.unavailable.add(l)

        # set the widget to be reactive to events
        self.set_flags(gtk.CAN_FOCUS)
        event.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                         gtk.gdk.BUTTON_RELEASE_MASK|
                         gtk.gdk.KEY_RELEASE_MASK|
                         gtk.gdk.KEY_PRESS_MASK|
                         gtk.gdk.ENTER_NOTIFY_MASK|
                         gtk.gdk.LEAVE_NOTIFY_MASK)

        # connect events to signal handlers
        event.connect('enter-notify-event', self._on_enter)
        event.connect('leave-notify-event', self._on_leave)
        event.connect('button-press-event', self._on_press)
        event.connect('button-release-event', self._on_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)

        # data 
        self.distro = distro
        self.icons = icons

        self.appname = None
        self.thumb_url = None
        self.large_url = None

        # state tracking
        self.ready = False
        self.screenshot_available = False
        self.alpha = 0.0

        # convienience class for handling the downloading (or not) of any screenshot
        self.loader = ImageDownloader()
        self.loader.connect('image-url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('image-download-complete', self._on_screenshot_download_complete)

    # signal handlers
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
        if (event.keyval in (gtk.keysyms.space, 
                             gtk.keysyms.Return, 
                             gtk.keysyms.KP_Enter) and 
            self.get_is_actionable()):
            self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421) and self.get_is_actionable():
            self.set_state(gtk.STATE_NORMAL)
            self._show_image_dialog()
        return

    def _on_image_expose(self, widget, event):
        """ If the alpha value is less than 1, we override the normal draw
            for the GtkImage so we can draw with transparencey.
        """

        if widget.get_storage_type() != gtk.IMAGE_PIXBUF:
            return

        pb = widget.get_pixbuf()
        if not pb: return True

        a = widget.allocation
        cr = widget.window.cairo_create()

        cr.rectangle(a)
        cr.clip()

        # draw the pixbuf with the current alpha value
        cr.set_source_pixbuf(pb, a.x, a.y)
        cr.paint_with_alpha(self.alpha)
        return True

    def _fade_in(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.alpha += 0.05
        if self.alpha >= 1.0:
            self.alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _show_image_dialog(self):
        """ Displays the large screenshot in a seperate dialog window """

        url = self.large_url
        title = _("%s - Screenshot") % self.appname
        d = ShowImageDialog(
            title, url,
            self.distro.IMAGE_FULL_MISSING,
            os.path.join(self.loader.tmpdir, uri_to_filename(url)))
        d.run()
        d.destroy()
        return

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable: self.ready = True
        return

    def _on_screenshot_download_complete(self, loader, screenshot_path):

        def setter_cb(path):
            try:
                pb = gtk.gdk.pixbuf_new_from_file(path)
            except:
                LOG.warn('Screenshot downloaded but the file could not be opened.')
                return False

            self.image.set_size_request(-1, -1)
            self.image.set_from_pixbuf(pb)
            # start the fade in
            gobject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        gobject.idle_add(setter_cb, screenshot_path)
        return

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and the download has completed """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):

        """ Configures the ScreenshotView depending on whether there is a screenshot available. """

        if not available:
            if self.image.parent:
                self.eventbox.remove(self.image)
                self.eventbox.add(self.unavailable)
                # set the size of the unavailable placeholder
                # 160 pixels is the fixed width of the thumbnails
                self.unavailable.set_size_request(160, 100)
                self.unavailable.show_all()
                acc = self.get_accessible()
                acc.set_name(_('%s - No screenshot available') % self.appname)
        else:
            if self.unavailable.parent:
                self.eventbox.remove(self.unavailable)
                self.eventbox.add(self.image)
                self.image.show()
                acc = self.get_accessible()
                acc.set_name(_('%s - Screenshot') % self.appname)

        self.screenshot_available = available
        return
 
    def configure(self, app_details):

        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """

        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))

        self.clear()
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname
        self.thumbnail_url = app_details.thumbnail
        self.large_url = app_details.screenshot
        return

    def clear(self):

        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """

        self.screenshot_available = True
        self.ready = False
        self.alpha = 0.0

        if self.unavailable.parent:
            self.eventbox.remove(self.unavailable)
            self.eventbox.add(self.image)
            self.image.show()

        # set the loading animation (its a .gif so a our GtkImage happily renders the animation
        # without any fuss, NOTE this gif has a white background, i.e. it has no transparency
        # TODO: use a generic gtk.Spinner instead of this icon
        self.image.set_from_file(IMAGE_LOADING_INSTALLED)
        self.image.set_size_request(160, 100)
        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its 
            reachable, if so it downloads the thumbnail.
            If not, it emits "image-url-reachable" False, then exits.
        """
        
        self.loader.download_image(self.thumbnail_url)
        return

    def draw(self, cr, a, expose_area):
        """ Draws the thumbnail frame """

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


class Addon(gtk.HBox):
    """ Widget to select addons: CheckButton - Icon - Title (pkgname) """

    def __init__(self, db, icons, pkgname):
        gtk.HBox.__init__(self, spacing=mkit.SPACING_SMALL)
        #self.set_resize_mode(gtk.RESIZE_IMMEDIATE)
        self.connect("realize", self._on_realize)

        # data
        self.app = Application("", pkgname)
        self.app_details = self.app.get_details(db)

        # checkbutton
        self.checkbutton = gtk.CheckButton()
        self.checkbutton.pkgname = self.app.pkgname
        self.pack_start(self.checkbutton, False)

        # icon
        hbox = gtk.HBox(spacing=mkit.SPACING_MED)
        self.icon = gtk.Image()
        proposed_icon = self.app_details.icon
        if not proposed_icon or not icons.has_icon(proposed_icon):
            proposed_icon = MISSING_APP_ICON
        try:
            pixbuf = icons.load_icon(proposed_icon, 22, ())
            if pixbuf:
                pixbuf.scale_simple(22, 22, gtk.gdk.INTERP_BILINEAR)
            self.icon.set_from_pixbuf(pixbuf)
        except:
            LOG.warning("cant set icon for '%s' " % pkgname)
        hbox.pack_start(self.icon, False, False)

        self.more = mkit.HLinkButton("More Info")
        self.more.set_underline(True)
        self.pack_end(self.more, False)
        self.more.connect("clicked", self._on_more_clicked)

        # name
        title = self.app_details.display_name
        if len(title) >= 2:
            title = title[0].upper() + title[1:]
        a = gtk.Alignment()
        self.title = gtk.Label(title)
        self.title.set_alignment(0, 0.5)
        #self.title.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        #self.title.set_line_wrap(True)
        hbox.pack_start(self.title, False)
        self.checkbutton.add(hbox)

        # pkgname
        self.pkgname = gtk.Label()
        hbox.pack_start(self.pkgname, False)

        # a11y
        self.a11y = self.checkbutton.get_accessible()
        self.a11y.set_name(_("Add-on") + ':' + title + '(' + pkgname + ')')

    def _on_realize(self, widget):
        dark = self.style.dark[self.state].to_string()
        key_markup = '<span color="%s">(%s)</span>'
        self.pkgname.set_markup(key_markup  % (dark, self.checkbutton.pkgname))

    def _on_more_clicked(self, more_btn):
        a = self.get_ancestor(AppDetailsViewGtk)
        if not a: return
        a.show_app(self.app)
        return

    def get_active(self):
        return self.checkbutton.get_active()

    def set_active(self, is_active):
        self.checkbutton.set_active(is_active)

    def set_width(self, width):
        #print width
        return


class AddonsTable(gtk.VBox):
    """ Widget to display a table of addons. """
    
    def __init__(self, addons_manager):
        gtk.VBox.__init__(self)
        self.set_border_width(6)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache
        self.db = self.addons_manager.view.db
        self.icons = self.addons_manager.view.icons
        self.recommended_addons = None
        self.suggested_addons = None

        self.label = gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_alignment(0, 0.5)
        markup = _('<b><big>Add-ons</big></b>')
        self.label.set_markup(markup)

        self.expander = gtk.Expander()
        self.expander.set_label_widget(self.label)
        self.pack_start(self.expander, False)

        self.vbox = gtk.VBox(spacing=mkit.SPACING_SMALL)
        self.vbox.set_no_show_all(True)
        self.vbox.set_border_width(6)
        self.pack_start(self.vbox)

        self._reload = True
        self.expander.connect('notify::expanded', self._on_expand)
        return

    def _on_expand(self, expander, param):
        if not self.expander.get_expanded():
            self.vbox.hide_all()
        else:
            if self.vbox.get_no_show_all():
                self.vbox.set_no_show_all(False)
            self._fill()
        return

    def _fill(self):
        if not self.recommended_addons and not self.suggested_addons:
            return

        if not self._reload:
            self.vbox.show_all()
            return

        view_width = self.addons_manager.view.allocation.width

        # clear any existing addons
        for addon in self.vbox:
            self.vbox.remove(addon)

        # set the new addons
        for addon_name in self.recommended_addons + self.suggested_addons:
            try:
                pkg = self.cache[addon_name]
            except KeyError:
                continue

            addon = Addon(self.db, self.icons, addon_name)
            #addon.pkgname.connect("clicked", not yet suitable for use)
            addon.set_active(pkg.installed != None)
            addon.checkbutton.connect("toggled", self.addons_manager.mark_changes)
            self.vbox.pack_start(addon, False)
            addon.set_width(view_width)

        self._reload = False
        self.vbox.show_all()
        return

    def set_addons(self, addons):
        # FIXME: sort the addons in alphabetical order
        self.recommended_addons = addons[0]
        self.suggested_addons = addons[1]
        self._reload = True

        if not self.recommended_addons and not self.suggested_addons:
            self.hide()
        else:
            self.show()
            if self.expander.get_expanded():
                self._fill()
        return False

    def set_width(self, width):
        for child in self.vbox:
            child.set_width(width)
        return

    def draw(self, cr, a):
        if a.width <= 0: return
        cr.save()
        rr= mkit.ShapeRoundedRectangle()
        rr.layout(cr, a.x,a.y, a.x+a.width, a.y+a.height, radius=4)
        cr.set_source_rgba(*mkit.floats_from_gdkcolor_with_alpha(self.style.mid[0], 0.175))
        cr.fill()
        cr.set_line_width(1)
        rr.layout(cr, a.x+0.5,a.y+0.5, a.x+a.width-0.5, a.y+a.height-0.5, radius=4)
        cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.dark[0]))
        cr.stroke()
        cr.restore()
        return


class Reviews(gtk.VBox):

    __gsignals__ = {
        'new-review':(gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    ()),
        'report-abuse':(gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,)),
    }

    def __init__(self, parent):
        gtk.VBox.__init__(self)
        self.set_border_width(6)

        self._parent = parent
        self.reviews = []

        label = mkit.EtchedLabel()
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        markup = "<b><big>%s</big></b>" % _("Reviews")
        label.set_markup(markup)

        self.expander = gtk.Expander()
        self.expander.set_label_widget(label)

        self.new_review = mkit.VLinkButton(_("Write your own review"))
        self.new_review.set_internal_spacing(mkit.SPACING_MED)
        self.new_review.set_underline(True)

        expander_hb = gtk.HBox(spacing=mkit.SPACING_MED)
        self.pack_start(expander_hb, False)
        expander_hb.pack_start(self.expander, False)
        expander_hb.pack_end(self.new_review, False)

        self.vbox = gtk.VBox(spacing=mkit.SPACING_XLARGE)
        self.vbox.set_no_show_all(True)
        self.vbox.set_border_width(6)
        self.pack_start(self.vbox, padding=6)

        self._update = True
        self.expander.connect('notify::expanded', self._on_expand)
        self.expander.set_expanded(True)
        self.new_review.connect('clicked', lambda w: self.emit('new-review'))
        return

    def _get_person_from_config(self):
        cfg = get_config()
        if cfg.has_option("reviews", "username"):
            return cfg.get("reviews", "username")
        return None

    def _on_expand(self, expander, param):
        if not self.expander.get_expanded():
            self.vbox.hide_all()
        else:
            if self.vbox.get_no_show_all():
                self.vbox.set_no_show_all(False)

            if self._update:
                self._fill()
                self._update = False
                return
            self.vbox.show_all()
        return

    def _on_button_new_clicked(self, button):
        self.emit("new-review")

    def _fill(self):
        self.logged_in_person = self._get_person_from_config()
        if self.reviews:
            for r in self.reviews:
                pkgversion = self._parent.app_details.version
                review = Review(r, pkgversion, self.logged_in_person)
                self.vbox.pack_start(review)
        elif get_network_state() == NetState.NM_STATE_CONNECTED:
            self.vbox.pack_start(NoReviewYet())
        return

    def _be_the_first_to_review(self):
        s = _('Be the first to review it')
        self.new_review.set_label(s)
        return
    
    def _any_reviews_current_user(self):
        for review in self.reviews:
            if self.logged_in_person == review.reviewer_username:
                return True
        return False

    def finished(self):
        #print 'Review count: %s' % len(self.reviews)
        if not self.reviews:
            self._be_the_first_to_review()
        else:
            if self._any_reviews_current_user():
                self.new_review.set_label(_("Write another review"))
            else:
                self.new_review.set_label(_("Write your own review"))
            if self.expander.get_expanded():
                self._fill()
                self.vbox.show_all()
                self._update = False
        return

    def set_width(self, w):
        for r in self.vbox:
            r.body.set_size_request(w, -1)
        return

    def add_review(self, review):
        self.reviews.append(review)
        self._update = True
        return

    def clear(self):
        self.reviews = []
        for review in self.vbox:
            review.destroy()

    def draw(self, cr, a):
        cr.save()
        rr = mkit.ShapeRoundedRectangle()
        r, g, b = mkit.floats_from_string('#FFE879')
        rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=4)
        cr.set_source_rgba(r,g,b,0.2)
        cr.fill_preserve()

        lin = cairo.LinearGradient(0, a.y, 0, a.y+150)
        lin.add_color_stop_rgba(0, r,g,b, 0.3)
        lin.add_color_stop_rgba(1, r,g,b, 0.0)
        
        cr.set_source(lin)
        cr.fill()

        cr.set_source_rgba(*mkit.floats_from_string('#E6BC26')+(0.5,))
        rr.layout(cr, a.x+0.5, a.y+0.5, a.x+a.width-0.5, a.y+a.height-0.5, radius=4)
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

        if not self.expander.get_expanded(): return

        for r in self.vbox:
            r.draw(cr, r.allocation)
        return

    def get_reviews(self):
        return filter(lambda r: not isinstance(r, (EmbeddedMessage, NoReviewYet)) and isinstance(r, Review), self.vbox.get_children())

class Review(gtk.VBox):
    
    def __init__(self, review_data=None, app_version=None, logged_in_person=None):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_LARGE)

        self.header = gtk.HBox(spacing=mkit.SPACING_MED)
        self.body = gtk.VBox()
        self.footer = gtk.HBox()

        self.pack_start(self.header, False)
        self.pack_start(self.body, False)
        self.pack_start(self.footer, False)
        
        self.logged_in_person = logged_in_person

        if review_data:
            self.id = review_data.id
            rating = review_data.rating 
            self.person = review_data.reviewer_username
            summary = review_data.summary
            text = review_data.review_text
            date = review_data.date_created
            app_name = review_data.app_name
            # some older version of the server do not set the version
            review_version = getattr(review_data, "version", "")
            self._build(rating, self.person, summary, text, date, app_name, review_version, app_version)

        self.body.connect('size-allocate', self._on_allocate)
        return

    def _on_allocate(self, widget, allocation):
        for child in self.body:
            child.set_size_request(allocation.width, -1)
        return

    def _on_report_abuse_clicked(self, button):
        reviews = self.get_ancestor(Reviews)
        if reviews:
            reviews.emit("report-abuse", self.id)

    def _build(self, rating, person, summary, text, date, app_name, review_version, app_version):
        # all the arguments are may need markup escape, depening on if
        # they are used as text or markup
        if person == self.logged_in_person:
            m = "%s %s" % (_("This is your review, submitted on"),
                                glib.markup_escape_text(date))
        else:
            m = "<b>%s</b>, %s" % (glib.markup_escape_text(person),
                                glib.markup_escape_text(date))
        who_what_when = gtk.Label(m)
        who_what_when.set_use_markup(True)

        summary = gtk.Label('<b>%s</b>' % glib.markup_escape_text(summary))
        summary.set_use_markup(True)

        text = gtk.Label(text)
        text.set_line_wrap(True)
        text.set_selectable(True)
        text.set_alignment(0, 0)
        
        self.header.pack_start(StarRating(rating), False)
        self.header.pack_start(summary, False)
        self.header.pack_end(who_what_when, False)
        #self.header.pack_end(gtk.Label(self.rating), False)
        self.body.pack_start(text, False)
        
        #if review version is different to version of app being displayed, 
        # alert user
        if (review_version and 
            upstream_version_compare(review_version, app_version) != 0):
            version_string = _("This review was written for a different version of %(app_name)s (Version: %(version)s)") % { 
                'app_name' : app_name,
                'version' : glib.markup_escape_text(upstream_version(review_version))
                }
            version_lbl = gtk.Label("<small><i>%s</i></small>" % version_string)
            version_lbl.set_use_markup(True)
            version_lbl.set_padding(0,3)
            self.footer.pack_start(version_lbl, False)
        
        #like = mkit.VLinkButton('<small>%s</small>' % _('This review was useful'))
        #like.set_underline(True)
        #self.footer.pack_start(like, False)

        # Translators: Flags should be translated in the sense of
        #  "Report as inappropriate"
        self.complain = mkit.VLinkButton('<small>%s</small>' % _('Flag'))
        self.complain.set_underline(True)
        self.footer.pack_end(self.complain, False)
        self.complain.connect('clicked', self._on_report_abuse_clicked)
        return

    def draw(self, cr, a):
        cr.save()
        rr = mkit.ShapeRoundedRectangle()
        rr.layout(cr, a.x-6, a.y-5, a.x+a.width+6, a.y+a.height+5, radius=3)
        if self.person == self.logged_in_person:
            cr.set_source_rgba(0.8,0.8,0.8,0.5)
        else:
            cr.set_source_rgba(1,1,1,0.7)
        cr.fill()
        cr.set_source_rgb(*mkit.floats_from_string('#E6BC26'))
        rr.layout(cr, a.x-5.5, a.y-4.5, a.x+a.width+5.5, a.y+a.height+4.5, radius=3)
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

class NoReviewYet(Review):
    """ represents if there are no reviews yet """
    def __init__(self, *args, **kwargs):
        super(NoReviewYet, self).__init__(*args, **kwargs)
        # TRANSLATORS: displayed if there are no reviews yet
        self.body.pack_start(gtk.Label(_("None yet")))
    #def draw(self, cr, a):
    #    pass


class EmbeddedMessage(Review):

    def __init__(self, label, icon_name):
        Review.__init__(self)

        a = gtk.Alignment(0.5, 0.5)
        self.body.pack_start(a, False)

        hb = gtk.HBox(spacing=12)
        a.add(hb)

        i = gtk.image_new_from_icon_name(icon_name, gtk.ICON_SIZE_DIALOG)
        hb.pack_start(i)

        l = gtk.Label()
        l.set_markup(label)
        hb.pack_start(l)

        self.show_all()
        return


class AddonsStatusBar(StatusBar):
    
    def __init__(self, addons_manager):
        StatusBar.__init__(self, addons_manager.view)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache

        self.applying = False
        
        self.label_price = mkit.EtchedLabel(_("Free"))
        self.hbox.pack_start(self.label_price, False)
        
        self.hbuttonbox = gtk.HButtonBox()
        self.hbuttonbox.set_layout(gtk.BUTTONBOX_END)
        self.button_apply = gtk.Button(_("Apply Changes"))
        self.button_apply.connect("clicked", self._on_button_apply_clicked)
        self.button_cancel = gtk.Button(_("Cancel"))
        self.button_cancel.connect("clicked", self.addons_manager.restore)
        self.hbox.pack_end(self.button_apply, False)
        self.hbox.pack_end(self.button_cancel, False)
        #self.hbox.pack_start(self.hbuttonbox, False)

    def configure(self):
        # FIXME: addons are not always free, but the old implementation of determining price was buggy
        if not self.addons_manager.addons_to_install and not self.addons_manager.addons_to_remove:
            self.hide()
        else:
            self.button_apply.set_sensitive(True)
            self.button_cancel.set_sensitive(True)
            self.show()
    
    def _on_button_apply_clicked(self, button):
        self.applying = True
        self.button_apply.set_sensitive(False)
        self.button_cancel.set_sensitive(False)
        # these two lines are the magic that make it work
        self.view.addons_to_install = self.addons_manager.addons_to_install
        self.view.addons_to_remove = self.addons_manager.addons_to_remove
        AppDetailsViewBase.apply_changes(self.view)


class AddonsManager():
    def __init__(self, view):
        self.view = view

        # add-on handling
        self.table = AddonsTable(self)
        self.status_bar = AddonsStatusBar(self)
        self.addons_to_install = []
        self.addons_to_remove = []

    def mark_changes(self, checkbutton):
        addon = checkbutton.pkgname
        installed = self.view.cache[addon].installed
        if checkbutton.get_active():
            if addon not in self.addons_to_install and not installed:
                self.addons_to_install.append(addon)
            if addon in self.addons_to_remove:
                self.addons_to_remove.remove(addon)
        else:
            if addon not in self.addons_to_remove and installed:
                self.addons_to_remove.append(addon)
            if addon in self.addons_to_install:
                self.addons_to_install.remove(addon)
        self.status_bar.configure()
        gobject.idle_add(self.view.update_totalsize)

    def configure(self, pkgname, update_addons=True):
        self.addons_to_install = []
        self.addons_to_remove = []
        if update_addons:
            self.addons = self.view.cache.get_addons(pkgname)
            self.table.set_addons(self.addons)
        self.status_bar.configure()

    def restore(self, *button):
        self.addons_to_install = []
        self.addons_to_remove = []
        self.configure(self.view.app.pkgname)
        gobject.idle_add(self.view.update_totalsize)


class AppDetailsViewGtk(gtk.Viewport, AppDetailsViewBase):

    """ The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 48 # gtk.ICON_SIZE_DIALOG ?

    # need to include application-request-action here also since we are multiple-inheriting
    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
                    "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, )),
                    'application-request-action' : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, str),
                                       ),
                    'purchase-requested' : (gobject.SIGNAL_RUN_LAST,
                                            gobject.TYPE_NONE,
                                            (gobject.TYPE_PYOBJECT,
                                             str,)),
                    }


    def __init__(self, db, distro, icons, cache, datadir):
        AppDetailsViewBase.__init__(self, db, distro, icons, cache, datadir)
        gtk.Viewport.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)
        self.section = None
        self.adjustment_value = None

        # atk
        self.a11y = self.get_accessible()
        self.a11y.set_name("app_details pane")

        # aptdaemon
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

        # network status watcher
        watcher = get_network_watcher()
        watcher.connect("changed", self._on_net_state_changed)

        # app specific data
        self._same_app = False
        self.app = None
        self.app_details = None

        # addons manager
        self.addons_manager = AddonsManager(self)
        self.addons_to_install = self.addons_manager.addons_to_install
        self.addons_to_remove = self.addons_manager.addons_to_remove

        # switches
        # Bug #628714 check not only that gwibber is installed but that service accounts exist
        self._gwibber_is_available = GWIBBER_SERVICE_AVAILABLE
        #self._gwibber_is_available = os.path.exists("/usr/bin/gwibber-poster")        
        self._show_overlay = False
        self._overlay = gtk.gdk.pixbuf_new_from_file(INSTALLED_ICON)

        # page elements are packed into our very own lovely viewport
        self._layout_all()
        self.connect('size-allocate', self._on_allocate)
        self.vbox.connect('expose-event', self._on_expose)
        #self.main_frame.image.connect_after('expose-event', self._on_icon_expose)
        self.loaded = True
        return

    def _on_net_state_changed(self, watcher, state):
        if state == NetState.NM_STATE_DISCONNECTED:
            self._update_reviews_inactive_network()
        elif state == NetState.NM_STATE_CONNECTED:
            gobject.timeout_add(500, self._update_reviews_active_network)
        return

    def _check_for_reviews(self):
        # review stats is fast and syncronous
        stats = self.review_loader.get_review_stats(self.app)
        self._update_review_stats_widget(stats)
        # individual reviews is slow and async so we just queue it here
        reviews = self.review_loader.get_reviews(self.app,
                                                 self._reviews_ready_callback)

    def _update_review_stats_widget(self, stats):
        if stats:
            self.review_stats_widget.set_avg_rating(stats.ratings_average)
            self.review_stats_widget.set_nr_reviews(stats.ratings_total)
            self.review_stats_widget.show()
        else:
            self.review_stats_widget.hide()

    def _reviews_ready_callback(self, app, reviews):
        """ callback when new reviews are ready, cleans out the
            old ones
        """
        logging.info("_review_ready_callback: %s" % app)
        # avoid possible race if we already moved to a new app when
        # the reviews become ready 
        # (we only check for pkgname currently to avoid breaking on
        #  software-center totem)
        if self.app.pkgname != app.pkgname:
            return
        # clear out the old ones ...
        self.reviews.clear()
        # then add the new ones ...
        for review in reviews:
            self.reviews.add_review(review)
        # then update the stats (if needed). the caching can make them
        # wrong, so if the reviews we have in the list are more than the
        # stats we update manually
        old_stats = self.review_loader.get_review_stats(self.app)
        if ((old_stats is None and len(reviews) > 0) or
            (old_stats is not None and old_stats.ratings_total < len(reviews))):
            # generate new stats
            stats = ReviewStats(app)
            stats.ratings_total = len(reviews)
            if stats.ratings_total == 0:
                stats.ratings_average = 0
            else:
                stats.ratings_average = sum([x.rating for x in reviews]) / float(stats.ratings_total)
            # update UI
            self._update_review_stats_widget(stats)
            # update global stats cache as well
            self.review_loader.REVIEW_STATS_CACHE[app] = stats
        self.reviews.finished()

    def _on_allocate(self, widget, allocation):
        w = allocation.width

        max_title_width = w-84-self.review_stats_widget.allocation.width-5*EM
        self.main_frame.title.set_size_request(max_title_width, -1)
        self.main_frame.summary.set_size_request(max_title_width, -1)

        desc = self.app_desc.description
        size = desc.height_from_width(w-4*EM-166)
        if size:
            desc.set_size_request(*size)

        self.addon_view.set_width(w-4*EM)

        self.version_info.set_width(w-4*EM)
        self.license_info.set_width(w-4*EM)
        self.support_info.set_width(w-4*EM)

        self.reviews.set_width(w-5*EM)

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        a = widget.allocation
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip_preserve()
        #cr.clip()

        # base color
        cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.base[self.state]))
        cr.fill()

        if self.section:
            self.section.render(cr, a)

        # if the appicon is not that big draw a rectangle behind it
        # https://wiki.ubuntu.com/SoftwareCenter#software-icon-view
        if self.main_frame.image.get_storage_type() == gtk.IMAGE_PIXBUF:
            pb = self.main_frame.image.get_pixbuf()
            if pb.get_width() < 64 or pb.get_height() < 64:
                # draw icon frame
                self._draw_icon_frame(cr)
        else:
            # draw icon frame as well...
            self._draw_icon_frame(cr)

        self.app_desc.description.draw(widget, event)
        if self.pkg_statusbar.get_property('visible'):
            self.pkg_statusbar.draw(cr,
                                 self.pkg_statusbar.allocation,
                                 event.area)

        if self.addons_statusbar.get_property('visible'):
            self.addons_statusbar.draw(cr,
                                 self.addons_statusbar.allocation,
                                 event.area)

        if self.screenshot.get_property('visible'):
            self.screenshot.draw(cr, self.screenshot.allocation, expose_area)

        if self.homepage_btn.get_property('visible'):
            self.homepage_btn.draw(cr, self.homepage_btn.allocation, expose_area)
        if self.share_btn.get_property('visible'):
            self.share_btn.draw(cr, self.share_btn.allocation, expose_area)

        if self.usage.get_property('visible'):
            self.usage.draw(cr, self.usage.allocation)

        if self.addon_view.get_property('visible'):
            self.addon_view.draw(cr, self.addon_view.allocation)

        if self.reviews.get_property('visible'):
            self.reviews.draw(cr, self.reviews.allocation)

        del cr
        return

    def _on_icon_expose(self, widget, event):
        if not self._show_overlay: return
        a = widget.allocation
        cr = widget.window.cairo_create()
        pb = self._overlay
        cr.set_source_pixbuf(pb,
                             a.x+a.width-pb.get_width(),
                             a.y+a.height-pb.get_height())
        cr.paint()
        del cr
        return

    def _on_homepage_clicked(self, button):
        import webbrowser
        webbrowser.open_new_tab(self.app_details.website)
        return

    def _on_share_clicked(self, button):
        # TRANSLATORS: apt:%(pkgname) is the apt protocol
        msg = _("Check out %(appname)s! apt:%(pkgname)s") % {
                'appname' : self.app_details.display_name, 
                'pkgname' : self.app_details.pkgname }
        p = subprocess.Popen(["gwibber-poster", "-w", "-m", msg])
        # setup timeout handler to avoid zombies
        glib.timeout_add_seconds(1, lambda p: p.poll() is None, p)
        return

    def _full_redraw_cb(self):
        self.queue_draw()
        if self.adjustment_value is not None \
        and self.adjustment_value >= self.get_vadjustment().lower \
        and self.adjustment_value <= self.get_vadjustment().upper:
            self.get_vadjustment().set_value(self.adjustment_value)
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
        if self.adjustment_value is not None \
        and self.adjustment_value >= self.get_vadjustment().lower \
        and self.adjustment_value <= self.get_vadjustment().upper:
            self.get_vadjustment().set_value(self.adjustment_value)
        gobject.idle_add(self._full_redraw_cb)
        return

    def _layout_main_frame_header(self):
        # root vbox
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.vbox.set_border_width(mkit.BORDER_WIDTH_XLARGE)
        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox.set_redraw_on_allocate(False)

        # main framed section that contains all app details
        self.main_frame = mkit.FramedSectionAlt()
        self.main_frame.image.set_size_request(84, 84)
        self.main_frame.set_spacing(mkit.SPACING_LARGE)
        self.main_frame.header.set_spacing(mkit.SPACING_LARGE)
        self.main_frame.header_alignment.set_padding(mkit.SPACING_SMALL,
                                                   mkit.SPACING_SMALL,
                                                   0, 0)

        self.review_stats_widget = ReviewStatsContainer()
        align = gtk.Alignment(1, 0.5)
        align.add(self.review_stats_widget)
        self.main_frame.header.pack_start(align, False, False)

        self.main_frame.body.set_spacing(mkit.SPACING_XLARGE)
        self.vbox.pack_start(self.main_frame, False)

        # a11y for name/summary
        self.main_frame.header.set_property("can-focus", True)
        self.main_frame.header.a11y = self.main_frame.header.get_accessible()
        return

    def _layout_usage_counter(self):
        # if zeitgeist is installed,
        # the amount of times it was used
        self.usage = mkit.BubbleLabel()
        self.main_frame.header_vbox.pack_start(self.usage, False, padding=2)
        return

    def _layout_pkg_status_actions(self):
        # controls which are displayed if the app is installed
        self.pkg_statusbar = PackageStatusBar(self)
        self.main_frame.body.pack_start(self.pkg_statusbar, False)

        # the location of the app (if its installed)
        self.installed_where_hbox = gtk.HBox(spacing=mkit.SPACING_MED)
        self.main_frame.body.pack_start(self.installed_where_hbox)
        self.installed_where_hbox.a11y = self.installed_where_hbox.get_accessible()
        return

    def _layout_app_description(self):
        # framed section which contains the app description
        #self.app_desc_frame = mkit.FramedSection(xpadding=mkit.SPACING_XLARGE)
        #self.app_desc_frame.header_alignment.set_padding(0,0,0,0)
        #self.main_frame.body.pack_start(self.app_desc_frame, False)

        # the app desc hboc contains both the app desc on the left and the 
        # screenshot on the right
        app_desc_hb = gtk.HBox(spacing=mkit.SPACING_LARGE)
        self.main_frame.body.pack_start(app_desc_hb)

        # application description wigdets
        self.app_desc = AppDescription()
        app_desc_hb.pack_start(self.app_desc, False)

        # a11y for description
        self.app_desc.description.set_property("can-focus", True)
        self.app_desc.description.a11y = self.app_desc.description.get_accessible()

        # screenshot
        self.screenshot = ScreenshotView(self.distro, self.icons)
        app_desc_hb.pack_end(self.screenshot)

        # homepage link button
        self.homepage_btn = mkit.HLinkButton(_('Website'))
        self.homepage_btn.connect('clicked', self._on_homepage_clicked)
        self.homepage_btn.set_underline(True)
        self.app_desc.footer.pack_start(self.homepage_btn, False)

        # share app with microbloggers button
        self.share_btn = mkit.HLinkButton(_('Share...'))
        self.share_btn.set_underline(True)
        self.share_btn.set_tooltip_text(_('Share via a micro-blogging service...'))
        self.share_btn.connect('clicked', self._on_share_clicked)
        self.app_desc.footer.pack_start(self.share_btn, False)
        return

    def _layout_pkg_info(self):
        # package info
        self.info_keys = []

        info_table_vbox = gtk.VBox(spacing=mkit.SPACING_MED)
        self.main_frame.body.pack_start(info_table_vbox, False)

        self.totalsize_info = PackageInfo(_("Total size:"), self.info_keys)
        info_table_vbox.pack_start(self.totalsize_info, False)

        self.addons_statusbar = self.addons_manager.status_bar
        info_table_vbox.pack_start(self.addons_statusbar, False, padding=3)

        self.version_info = PackageInfo(_("Version:"), self.info_keys)
        info_table_vbox.pack_start(self.version_info, False)

        self.license_info = PackageInfo(_("License:"), self.info_keys)
        info_table_vbox.pack_start(self.license_info, False)

        self.support_info = PackageInfo(_("Updates:"), self.info_keys)
        info_table_vbox.pack_start(self.support_info, False)
        return

    def _layout_pkg_addons_actions(self):
        # addons manager
        self.addons_to_install = self.addons_manager.addons_to_install
        self.addons_to_remove = self.addons_manager.addons_to_remove
        self.addon_view = self.addons_manager.table
        self.main_frame.body.pack_start(self.addon_view, False)
        return

    def _layout_reviews(self):
        # reviews
        self.reviews = Reviews(self)
        self.reviews.connect("new-review", self._on_review_new)
        self.reviews.connect("report-abuse", self._on_review_report_abuse)
        self.main_frame.body.pack_start(self.reviews)
        return

    def _layout_all(self):
        # setup widgets
        self._layout_main_frame_header()
        self._layout_usage_counter()
        self._layout_pkg_status_actions()
        self._layout_app_description()
        self._layout_pkg_addons_actions()
        self._layout_pkg_info()
        self._layout_reviews()
        self.show_all()
        return

    def _on_review_new(self, button):
        self._review_write_new()

    def _on_review_report_abuse(self, button, review_id):
        self._review_report_abuse(str(review_id))

    def _update_title_markup(self, appname, summary):
        # make title font size fixed as they should look good compared to the 
        # icon (also fixed).
        big = 20*pango.SCALE
        title = '<b><span size="%s">%s</span></b>' % (big, appname)
        #summary = '<small>%s</small>' % summary

        # set app- icon, name and summary in the header
        self.main_frame.set_title(markup=title)
        self.main_frame.set_summary(markup=summary)

        # a11y for name/summary
        self.main_frame.header.a11y.set_name("Application: " + appname + ". Summary: " + summary)
        self.main_frame.header.a11y.set_role(atk.ROLE_PANEL)
        self.main_frame.header.grab_focus()
        return

    def _update_app_icon(self, app_details):

        def get_avg_color(pb):
            avg = pb.scale_simple(1, 1, gtk.gdk.INTERP_BILINEAR)
            rgb = Image.fromstring("RGB", (1,1), avg.get_pixels()).getpixel((0,0))
            return map(lambda x: x/255.0, rgb) # rgb to floats

        pb = self._get_icon_as_pixbuf(app_details)
        # should we show the green tick?
        #self._show_overlay = app_details.pkg_state == PKG_STATE_INSTALLED
        self.main_frame.set_icon_from_pixbuf(pb)

        # sample avg color of icon
        self.avg_icon_rgb = get_avg_color(pb)
        return

    def _update_layout_error_status(self, pkg_error):
        # if we have an error or if we need to enable a source, then hide everything else
        if pkg_error:
            self.addon_view.hide()
            self.reviews.hide()
            self.screenshot.hide()
            self.version_info.hide()
            self.license_info.hide()
            self.support_info.hide()
            self.totalsize_info.hide()
        else:
            self.addon_view.show()
            self.reviews.show()
            self.version_info.show()
            self.license_info.show()
            self.support_info.show()
            self.totalsize_info.show()
            self.screenshot.show()
        return

    def _update_app_description(self, app_details, appname):
        # format new app description
        if app_details.pkg_state == PKG_STATE_ERROR:
            description = app_details.error
        else:
            description = app_details.description
        if not description:
            description = " "
        self.app_desc.set_description(description, appname)
        # a11y for description
        #self.app_desc.body.a11y.set_name("Description: " + description)
        return

    def _update_description_footer_links(self, app_details):        
        # show or hide the homepage button and set uri if homepage specified
        if app_details.website:
            self.homepage_btn.show()
            self.homepage_btn.set_tooltip_text(app_details.website)
        else:
            self.homepage_btn.hide()

        # check if gwibber-poster is available, if so display Share... btn
        if (self._gwibber_is_available and 
            app_details.pkg_state not in (PKG_STATE_NOT_FOUND, PKG_STATE_NEEDS_SOURCE)):
            self.share_btn.show()
        else:
            self.share_btn.hide()
        return

    def _update_app_screenshot(self, app_details):
        # get screenshot urls and configure the ScreenshotView...
        if app_details.thumbnail and app_details.screenshot and not self._same_app:
            self.screenshot.configure(app_details)

            # then begin screenshot download and display sequence
            self.screenshot.download_and_display()
        return

    def _update_pkg_info_table(self, app_details):
        # set the strings in the package info table
        if app_details.version:
            version = '%s (%s)' % (app_details.version, app_details.pkgname)
        else:
            version = _("Unknown")
            # if the version is unknown, just hide the field
            self.version_info.hide()
        if app_details.license:
            license = app_details.license
        else:
            license = _("Unknown")
        if app_details.maintenance_status:
            support = app_details.maintenance_status
        else:
            support = _("Unknown")
        self.version_info.set_value(version)
        self.license_info.set_value(license)
        self.support_info.set_value(support)
        return

    def _update_addons(self, app_details):
        # refresh addons interface
        #self.addon_view.hide_all()
        if not app_details.error:
            self.addons_manager.configure(self.app_details.pkgname)

        # Update total size label
        gobject.timeout_add(500, self.update_totalsize, True)
        
        # Update addons state bar
        self.addons_statusbar.configure()
        return

    def _update_reviews(self, app_details):
        self.reviews.clear()

    def _update_reviews_inactive_network(self):
        if self.reviews.get_reviews():
            msg_exists = False
            for r in self.reviews.vbox:
                if isinstance(r, EmbeddedMessage):
                    msg_exists = True
                elif hasattr(r, 'complain'):
                    r.complain.set_sensitive(False)
            if not msg_exists:
                s = '<big><b>%s</b></big>\n%s' % ('No Network Connection',
                                                  'Only cached reviews can be displayed')
                m = EmbeddedMessage(s, 'network-offline')

                self.reviews.vbox.pack_start(m)
                self.reviews.vbox.reorder_child(m, 0)
        else:
            self.reviews.clear()
            s = '<big><b>%s</b></big>\n%s' % ('No Network Connection',
                                              'Unable to download application reviews')
            m = EmbeddedMessage(s, 'network-offline')
            self.reviews.vbox.pack_start(m)

        self.reviews.new_review.set_sensitive(False)
        return

    def _update_reviews_active_network(self):
        for r in self.reviews.vbox:
            if isinstance(r, (EmbeddedMessage, NoReviewYet)):
                r.destroy()
            if hasattr(r, 'complain'):
                r.complain.set_sensitive(True)

        if not self.reviews.get_reviews():
            self._check_for_reviews()

        self.reviews.new_review.set_sensitive(True)
        return

    def _update_all(self, app_details):
        pkg_ambiguous_error = app_details.pkg_state in (PKG_STATE_NOT_FOUND, PKG_STATE_NEEDS_SOURCE)

        appname = gobject.markup_escape_text(app_details.display_name)

        if app_details.pkg_state == PKG_STATE_NOT_FOUND:
            summary = app_details._error_not_found
        else:
            summary = app_details.display_summary
        if not summary:
            summary = ""

        self._update_title_markup(appname, summary)
        self._update_app_icon(app_details)
        self._update_layout_error_status(pkg_ambiguous_error)
        self._update_app_description(app_details, appname)
        self._update_description_footer_links(app_details)
        self._update_app_screenshot(app_details)
        self._update_pkg_info_table(app_details)
        self._update_addons(app_details)
#        self._update_reviews(app_details)

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

        # show where it is
        self._configure_where_is_it()

        # async query zeitgeist and rnr
        self.get_usage_counter()

        self.reviews.clear()
        if get_network_state() == NetState.NM_STATE_DISCONNECTED:
            self._update_reviews_inactive_network()
        else:
            self._update_reviews_active_network()
        return

    def _update_minimal(self, app_details):
        pkg_ambiguous_error = app_details.pkg_state in (PKG_STATE_NOT_FOUND, PKG_STATE_NEEDS_SOURCE)

        appname = gobject.markup_escape_text(app_details.display_name)

        if app_details.pkg_state == PKG_STATE_NOT_FOUND:
            summary = app_details._error_not_found
        else:
            summary = app_details.display_summary
        if not summary:
            summary = ""

        self._update_title_markup(appname, summary)
        self._update_app_icon(app_details)
        self._update_layout_error_status(pkg_ambiguous_error)
        if not self.app_desc.description.order:
            self._update_app_description(app_details, appname)
            self._update_description_footer_links(app_details)
        self._update_pkg_info_table(app_details)
        self._update_addons(app_details)

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

        # show where it is
        self._configure_where_is_it()
        return

    def _configure_where_is_it(self):
        # disable where-is-it under Unity as it does not apply there
        if is_unity_running():
            return
        # remove old content
        self.installed_where_hbox.foreach(lambda c: c.destroy())
        self.installed_where_hbox.set_property("can-focus", False)
        self.installed_where_hbox.a11y.set_name('')
        # see if we have the location if its installed
        if self.app_details.pkg_state == PKG_STATE_INSTALLED:
            # first try the desktop file from the DB, then see if
            # there is a local desktop file with the same name as 
            # the package
            searcher = GMenuSearcher()
            desktop_file = None
            pkgname = self.app_details.pkgname
            for p in [self.app_details.desktop_file,
                      "/usr/share/applications/%s.desktop" % pkgname]:
                if os.path.exists(p):
                    desktop_file = p
                    break
            where = searcher.get_main_menu_path(desktop_file)
            if not where:
                return
            label = gtk.Label(_("Find it in the menu: "))
            self.installed_where_hbox.pack_start(label, False, False)
            for (i, item) in enumerate(where):
                iconname = item.get_icon()
                # check icontheme first
                if iconname and self.icons.has_icon(iconname) and i > 0:
                    image = gtk.Image()
                    image.set_from_icon_name(iconname, gtk.ICON_SIZE_SMALL_TOOLBAR)
                    self.installed_where_hbox.pack_start(image, False, False)
                # then see if its a path to a file on disk
                elif iconname and os.path.exists(iconname):
                    image = gtk.Image()
                    pb = gtk.gdk.pixbuf_new_from_file_at_size(iconname, 18, 18)
                    if pb:
                        image.set_from_pixbuf(pb)
                    self.installed_where_hbox.pack_start(image, False, False)

                label_name = gtk.Label()
                if item.get_type() == gmenu.TYPE_ENTRY:
                    label_name.set_text(item.get_display_name())
                else:
                    label_name.set_text(item.get_name())
                self.installed_where_hbox.pack_start(label_name, False, False)
                if i+1 < len(where):
                    right_arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE)
                    self.installed_where_hbox.pack_start(right_arrow, 
                                                         False, False)

            # create our a11y text
            a11y_text = ""
            for widget in self.installed_where_hbox:
                if isinstance(widget, gtk.Label):
                    a11y_text += ' > ' + widget.get_text()
            self.installed_where_hbox.a11y.set_name(a11y_text)
            self.installed_where_hbox.set_property("can-focus", True)

            self.installed_where_hbox.show_all()

    # public API
    # FIXME:  port to AppDetailsViewBase as
    #         AppDetailsViewBase.show_app(self, app)
    def show_app(self, app):
        LOG.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            LOG.debug("no app selected")
            return

        # set button sensitive again
        self.pkg_statusbar.button.set_sensitive(True)

        # init data
        old_details = self.app_details
        self.app = app
        self.app_details = app.get_details(self.db)
        self._same_app = old_details and self.app_details.same_app(old_details)

        # for compat with the base class
        self.appdetails = self.app_details
        
        # layout page
        if self._same_app:
            self._update_minimal(self.app_details)
        else:
            # reset view to top left
            self.get_vadjustment().set_value(0)
            self.get_hadjustment().set_value(0)

            self._update_all(self.app_details)

        self.emit("selected", self.app)
        return

    # public interface
    def use_this_source(self):
        if self.app_details.channelfile and self.app_details._unavailable_channel():
            self.backend.enable_channel(self.app_details.channelfile)
        elif self.app_details.component:
            components = self.app_details.component.split('&')
            for component in components:
                self.backend.enable_component(component)

    # internal callback
    def _update_interface_on_trans_ended(self, result):
        state = self.pkg_statusbar.pkg_state

        # handle purchase: install purchased has multiple steps
        if (state == PKG_STATE_INSTALLING_PURCHASED and 
            result and
            not result.pkgname):
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLING_PURCHASED)
        elif (state == PKG_STATE_INSTALLING_PURCHASED and 
              result and
              result.pkgname):
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
        # normal states
        elif state == PKG_STATE_REMOVING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_UNINSTALLED)
        elif state == PKG_STATE_INSTALLING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
        elif state == PKG_STATE_UPGRADING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
        # addons modified
        elif self.addons_statusbar.applying:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
            self.addons_manager.configure(self.app_details.name, False)
            self.addons_statusbar.configure()

        self.adjustment_value = None
        
        if self.addons_statusbar.applying:
            self.addons_statusbar.applying = False

        return False

    def _on_transaction_started(self, backend, pkgname, appname):
        if self.addons_statusbar.applying:
            self.pkg_statusbar.configure(self.app_details, APP_ACTION_APPLY)
            return

        state = self.pkg_statusbar.pkg_state
        LOG.debug("_on_transaction_started %s" % state)
        if state == PKG_STATE_NEEDS_PURCHASE:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLING_PURCHASED)
        elif state == PKG_STATE_UNINSTALLED:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLING)
        elif state == PKG_STATE_INSTALLED:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_REMOVING)
        elif state == PKG_STATE_UPGRADABLE:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_UPGRADING)
        elif state == PKG_STATE_REINSTALLABLE:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLING)
            # FIXME: is there a way to tell if we are installing/removing?
            # we will assume that it is being installed, but this means that during removals we get the text "Installing.."
            # self.pkg_statusbar.configure(self.app_details, PKG_STATE_REMOVING)
        return

    def _on_transaction_stopped(self, backend, result):
        self.pkg_statusbar.progress.hide()
        self._update_interface_on_trans_ended(result)
        return

    def _on_transaction_finished(self, backend, result):
        self.pkg_statusbar.progress.hide()
        self._update_interface_on_trans_ended(result)
        return

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if self.app_details and self.app_details.pkgname and self.app_details.pkgname == pkgname:
            if not self.pkg_statusbar.progress.get_property('visible'):
                self.pkg_statusbar.button.hide()
                self.pkg_statusbar.progress.show()
            if pkgname in backend.pending_transactions:
                self.pkg_statusbar.progress.set_fraction(progress/100.0)
            if progress >= 100:
                self.pkg_statusbar.progress.set_fraction(1)
                self.adjustment_value = self.get_vadjustment().get_value()
        return

    #def _draw_icon_inset_frame(self, cr):
        ## draw small or no icon background
        #a = self.main_frame.image.allocation

        #rr = mkit.ShapeRoundedRectangle()

        #cr.save()
        #r,g,b = mkit.floats_from_gdkcolor(self.style.dark[self.state])
        #rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=3)

        #lin = cairo.LinearGradient(0, a.y, 0, a.y+a.height)
        #lin.add_color_stop_rgba(0.0, r, g, b, 0.3)
        #lin.add_color_stop_rgba(1.0, r, g, b, 0.1)
        #cr.set_source(lin)
        #cr.fill()

        ## line width should be 0.05em, as per spec
        #line_width = max(1, int(EM*0.05+0.5))
        ## if line_width an odd number we need to align to the pixel grid
        #if line_width % 2:
            #cr.translate(0.5, 0.5)
        #cr.set_line_width(line_width)

        #cr.set_source_rgba(*mkit.floats_from_gdkcolor_with_alpha(self.style.light[self.state], 0.55))
        #rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height+1, radius=3)
        #cr.stroke()

        #cr.set_source_rgb(r, g, b)
        #rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=3)
        #cr.stroke_preserve()
        #cr.stroke_preserve()

        #cr.clip()

        #rr.layout(cr, a.x+1, a.y+1, a.x+a.width-1, a.y+a.height-1, radius=2.5)
        #cr.set_source_rgba(r, g, b, 0.35)
        #cr.stroke()

        #rr.layout(cr, a.x+2, a.y+2, a.x+a.width-2, a.y+a.height-2, radius=2)
        #cr.set_source_rgba(r, g, b, 0.1)
        #cr.stroke()

        #cr.restore()
        #return

    def _get_xy_icon_position_on_screen(self):
        """ helper for unity dbus support to get the x,y position of
            the appicon on the screen
        """
        # find toplevel parent
        parent = self
        while parent.get_parent():
            parent = parent.get_parent()
        # get x, y relative to toplevel
        (x,y) = self.app_info.image.translate_coordinates(parent, 0, 0)
        # get toplevel window position
        (px, py) = parent.get_position()
        return (px+x, py+y)

    def _draw_icon_frame(self, cr):
        # draw small or no icon background
        a = self.main_frame.image.allocation
        rr = mkit.ShapeRoundedRectangle()

        cr.save()
        rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=6)
        r, g, b = self.avg_icon_rgb
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()

        lin = cairo.LinearGradient(0, a.y, 0, a.y+a.height)
        lin.add_color_stop_rgba(0, 1,1,1, 0.6)
        lin.add_color_stop_rgba(1, 1,1,1, 0.7)

        cr.set_source(lin)
        cr.fill_preserve()

        cr.set_source_rgba(r, g, b, 0.75)
        cr.stroke()

        cr.restore()
        return
        
    def _get_icon_as_pixbuf(self, app_details):
        if app_details.icon:
            if self.icons.has_icon(app_details.icon):
                try:
                    return self.icons.load_icon(app_details.icon, 84, 0)
                except glib.GError, e:
                    logging.warn("failed to load '%s'" % app_details.icon)
                    return self.icons.load_icon(MISSING_APP_ICON, 84, 0)
            elif app_details.icon_needs_download and app_details.icon_url:
                LOG.debug("did not find the icon locally, must download it")

                def on_image_download_complete(downloader, image_file_path):
                    # when the download is complete, replace the icon in the view with the downloaded one
                    pb = gtk.gdk.pixbuf_new_from_file(image_file_path)
                    self.main_frame.set_icon_from_pixbuf(pb)
                    
                icon_file_path = os.path.join(SOFTWARE_CENTER_ICON_CACHE_DIR, app_details.icon_file_name)
                image_downloader = ImageDownloader()
                image_downloader.connect('image-download-complete', on_image_download_complete)
                image_downloader.download_image(app_details.icon_url, icon_file_path)
        return self.icons.load_icon(MISSING_APP_ICON, 84, 0)
    
    def update_totalsize(self, hide=False):
        def pkg_downloaded(pkg_version):
            filename = os.path.basename(pkg_version.filename)
            # FIXME: use relative path here
            return os.path.exists("/var/cache/apt/archives/" + filename)

        if not self.totalsize_info.get_property('visible'):
            return False
        elif hide:
            self.totalsize_info.hide_all()
        while gtk.events_pending():
            gtk.main_iteration()
        
        pkgs_to_install = []
        pkgs_to_remove = []
        total_download_size = 0 # in kB
        total_install_size = 0 # in kB
        label_string = ""
        
        try:
            pkg = self.cache[self.app_details.pkgname]
        except KeyError:
            self.totalsize_info.hide_all()
            return False
        version = pkg.installed
        if version == None:
            version = max(pkg.versions)
            deps_inst = self.cache.try_install_and_get_all_deps_installed(pkg)
            for dep in deps_inst:
                if self.cache[dep].installed == None:
                    dep_version = max(self.cache[dep].versions)
                    pkgs_to_install.append(dep_version)
            deps_remove = self.cache.try_install_and_get_all_deps_removed(pkg)
            for dep in deps_remove:
                if self.cache[dep].is_installed:
                    dep_version = self.cache[dep].installed
                    pkgs_to_remove.append(dep_version)
            pkgs_to_install.append(version)
        
        for addon in self.addons_manager.addons_to_install:
            version = max(self.cache[addon].versions)
            pkgs_to_install.append(version)
            deps_inst = self.cache.try_install_and_get_all_deps_installed(self.cache[addon])
            for dep in deps_inst:
                if self.cache[dep].installed == None:
                    version = max(self.cache[dep].versions)
                    pkgs_to_install.append(version)
            deps_remove = self.cache.try_install_and_get_all_deps_removed(self.cache[addon])
            for dep in deps_remove:
                if self.cache[dep].installed != None:
                    version = self.cache[dep].installed
                    pkgs_to_remove.append(version)
        for addon in self.addons_manager.addons_to_remove:
            version = self.cache[addon].installed
            pkgs_to_remove.append(version)
            deps_inst = self.cache.try_install_and_get_all_deps_installed(self.cache[addon])
            for dep in deps_inst:
                if self.cache[dep].installed == None:
                    version = max(self.cache[dep].versions)
                    pkgs_to_install.append(version)
            deps_remove = self.cache.try_install_and_get_all_deps_removed(self.cache[addon])
            for dep in deps_remove:
                if self.cache[dep].installed != None:
                    version = self.cache[dep].installed
                    pkgs_to_remove.append(version)

        pkgs_to_install = list(set(pkgs_to_install))
        pkgs_to_remove = list(set(pkgs_to_remove))
            
        for pkg in pkgs_to_install:
            if not pkg_downloaded(pkg) and not pkg.package.installed:
                total_download_size += pkg.size
            total_install_size += pkg.installed_size
        for pkg in pkgs_to_remove:
            total_install_size -= pkg.installed_size
        
        if total_download_size > 0:
            download_size = apt_pkg.size_to_str(total_download_size)
            label_string += _("%sB to download, ") % (download_size)
        if total_install_size > 0:
            install_size = apt_pkg.size_to_str(total_install_size)
            label_string += _("%sB when installed") % (install_size)
        elif (total_install_size == 0 and
              self.app_details.pkg_state == PKG_STATE_INSTALLED and
              not self.addons_manager.addons_to_install and
              not self.addons_manager.addons_to_remove):
            pkg = self.cache[self.app_details.pkgname].installed
            install_size = apt_pkg.size_to_str(pkg.installed_size)
            # FIXME: this is not really a good indication of the size on disk
            label_string += _("%sB on disk") % (install_size)
        elif total_install_size < 0:
            remove_size = apt_pkg.size_to_str(-total_install_size)
            label_string += _("%sB to be freed") % (remove_size)
        
        if label_string == "":
            self.totalsize_info.hide_all()
        else:
            self.totalsize_info.set_value(label_string)
            self.totalsize_info.show_all()
        return False

    def set_section(self, section):
        self.section = section
        return
        
    def get_usage_counter(self):
        """ try to get the usage counter from zeitgeist """
        def _zeitgeist_callback(counter):
            LOG.debug("zeitgeist usage: %s" % counter)
            if counter == 0:
                # this probably means we just have no idea about it,
                # so instead of saying "Used: never" we just return 
                # this can go away when zeitgeist captures more events
                # --there are still cases when we really do want to hide this
                self.usage.hide()
                return
            label_string = gettext.ngettext("Used: one time",
                                            "Used: %(amount)s times",
                                            counter) % { 'amount' : counter, }
            self.usage.set_text('<small>%s</small>' % label_string)
            self.usage.show()

        # try to get it
        zeitgeist_singleton.get_usage_counter(
            self.app_details.desktop_file, _zeitgeist_callback)


if __name__ == "__main__":
    def _show_app(view):
        if view.app.pkgname == "totem":
            view.show_app(Application("Pithos", "pithos"))
        else:
            view.show_app(Application("Movie Player", "totem"))
        return True
    
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
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppDetailsViewGtk(db, distro, icons, cache, datadir)
    from softwarecenter.db.application import Application
    #view.show_app(Application("Pay App Example", "pay-app"))
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
    win.set_size_request(800,600)
    win.show_all()

    # keep it spinning to test for re-draw issues and memleaks
    glib.timeout_add_seconds(1, _show_app, view)
    gtk.main()
