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
import tempfile
import xapian
import cairo

from gettext import gettext as _
import apt_pkg
from softwarecenter.backend import get_install_backend
from softwarecenter.db.application import AppDetails, Application
from softwarecenter.enums import *
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR
from softwarecenter.utils import ImageDownloader, GMenuSearcher
from softwarecenter.gwibber_helper import GWIBBER_SERVICE_AVAILABLE

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

LOG = logging.getLogger("softwarecenter.view.appdetailsview")


class StatusBar(gtk.Alignment):
    
    def __init__(self, view):
        gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)
        self.set_redraw_on_allocate(False)
        self.set_padding(mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL,
                         mkit.SPACING_SMALL+2,
                         mkit.SPACING_SMALL)

        self.hbox = gtk.HBox(spacing=mkit.SPACING_LARGE)
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
        return

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
        self.progress.hide()

        self.fill_color = COLOR_GREEN_FILL
        self.line_color = COLOR_GREEN_OUTLINE

        if state in (PKG_STATE_INSTALLING,
                     PKG_STATE_INSTALLING_PURCHASED,
                     PKG_STATE_REMOVING,
                     PKG_STATE_UPGRADING,
                     APP_ACTION_APPLY):
            self.button.hide()
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

        # FIXME:  Use a gtk.Action for the Install/Remove/Buy/Add Source/Update Now action
        #         so that all UI controls (menu item, applist view button and appdetails
        #         view button) are managed centrally:  button text, button sensitivity,
        #         and the associated callback.
        if state == PKG_STATE_INSTALLING:
            self.set_label(_('Installing...'))
            #self.set_button_label(_('Install'))
        elif state == PKG_STATE_INSTALLING_PURCHASED:
            self.set_label(_(u'Installing purchase\u2026'))
            #self.set_button_label(_('Install'))
        elif state == PKG_STATE_REMOVING:
            self.set_label(_('Removing...'))
            #self.set_button_label(_('Remove'))
        elif state == PKG_STATE_UPGRADING:
            self.set_label(_('Upgrading...'))
            #self.set_button_label(_('Upgrade Available'))
        elif state == PKG_STATE_INSTALLED:
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
            # FIXME:  need to determine the currency dynamically once we can
            #         get that info from the software-center-agent/payments service.
            # NOTE:  the currency string for this label is purposely not translatable
            #        when hardcoded, since it (currently) won't vary based on locale
            #        and as such we don't want it translated
            self.set_label("US$ %s" % app_details.price)
            self.set_button_label(_(u'Buy\u2026'))
        elif state == PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED:
            purchase_date = str(app_details.purchase_date).split()[0]
            self.set_label(_('Purchased on %s' % purchase_date))
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UNINSTALLED:
            if app_details.price:
                self.set_label(app_details.price)
            else:
                self.set_label(_("Free"))
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_REINSTALLABLE:
            if app_details.price:
                self.set_label(app_details.price)
            else:
                self.set_label("")
            self.set_button_label(_('Reinstall'))
        elif state == PKG_STATE_UPGRADABLE:
            self.set_label(_('Upgrade Available'))
            self.set_button_label(_('Upgrade'))
        elif state == APP_ACTION_APPLY:
            self.set_label(_(u'Changing Add-ons\u2026'))
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
                # FIXME: deal with the EULA stuff
                self.set_button_label(_("Use This Source"))
            # check if it comes from a non-enabled component
            elif self.app_details._unavailable_component():
                # FIXME: use a proper message here, but we are in string freeze
                self.set_button_label(_("Use This Source"))
            elif self.app_details._available_for_our_arch():
                self.set_button_label(_("Update Now"))
            self.fill_color = COLOR_YELLOW_FILL
            self.line_color = COLOR_YELLOW_OUTLINE
        if (self.app_details.warning and not self.app_details.error and
           not state in (PKG_STATE_INSTALLING, PKG_STATE_INSTALLING_PURCHASED,
           PKG_STATE_REMOVING, PKG_STATE_UPGRADING, APP_ACTION_APPLY)):
            self.set_label(self.app_details.warning)
        return


class AppDescription(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_LARGE)

        self.body = gtk.VBox()
        self.footer = gtk.HBox(spacing=mkit.SPACING_MED)

        self.pack_start(self.body, False)
        self.pack_start(self.footer, False)
        self.show_all()

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
        a.set_size_request(max_lw+3*mkit.EM, -1)
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
        self.value_label.set_text(value)
        self.a11y.set_name(self.key + ' ' + value)

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
        return

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

        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """

        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))

        self.clear()
        self.appname = app_details.display_name
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
        self.image.set_from_file(AppDetailsViewGtk.IMAGE_LOADING_INSTALLED)
        self.image.set_size_request(160, 100)
        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its 
            reachable, if so it downloads the thumbnail.
            If not, it emits "image-url-reachable" False, then exits.
        """

        self.loader.download_image(self.thumbnail_url,
                                   tempfile.NamedTemporaryFile(prefix="s-c-screenshot").name)
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
        gtk.HBox.__init__(self, spacing=mkit.SPACING_LARGE)

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

        # name
        title = self.app_details.display_name
        if len(title) >= 2:
            title = title[0].upper() + title[1:]
        self.title = gtk.Label(title)
        self.title.set_line_wrap(True)
        hbox.pack_start(self.title, False)
        self.checkbutton.add(hbox)

        # pkgname
        self.pkgname = gtk.Label()
        hbox.pack_start(self.pkgname, False)

    def _on_realize(self, widget):
        dark = self.style.dark[self.state].to_string()
        key_markup = '<span color="%s">(%s)</span>'
        self.pkgname.set_markup(key_markup  % (dark, self.checkbutton.pkgname))

    def get_active(self):
        return self.checkbutton.get_active()

    def set_active(self, is_active):
        self.checkbutton.set_active(is_active)    

class AddonsTable(gtk.VBox):
    """ Widget to display a table of addons. """
    
    def __init__(self, addons_manager):
        gtk.VBox.__init__(self, False, mkit.SPACING_MED)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache
        self.db = self.addons_manager.view.db
        self.icons = self.addons_manager.view.icons
        self.recommended_addons = None
        self.suggested_addons = None
        self.connect("realize", self._on_realize)

        self.label = gtk.Label()
        self.label.set_use_markup(True)
        self.label.set_alignment(0, 0.5)
        self.pack_start(self.label, False, False)

    def _on_realize(self, widget):
        markup = _('<b><span color="%s">Add-ons</span></b>')
        color = self.label.style.dark[self.label.state].to_string()
        self.label.set_markup(markup % color)
    
    def set_addons(self, addons):
        # FIXME: sort the addons in alphabetical order
        self.recommended_addons = addons[0]
        self.suggested_addons = addons[1]

        if not self.recommended_addons and not self.suggested_addons:
            return

        # clear any existing addons
        for widget in self:
            if widget != self.label:
                self.remove(widget)

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
            self.pack_start(addon, False)
        self.show_all()
        return False

class AddonsStatusBar(StatusBar):
    
    def __init__(self, addons_manager):
        StatusBar.__init__(self, addons_manager.view)
        self.addons_manager = addons_manager
        self.addons_table = self.addons_manager.table
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
            self.show()
    
    def get_applying(self):
        return self.applying

    def set_applying(self, applying):
        self.applying = applying
    
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

    def configure(self, pkgname):
        self.addons_to_install = []
        self.addons_to_remove = []
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

    # FIXME: use relative path here
    INSTALLED_ICON = "/usr/share/software-center/icons/software-center-installed.png"
    # TODO: use a generic gtk.Spinner instead of this icon
    IMAGE_LOADING = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading.gif"
    IMAGE_LOADING_INSTALLED = "/usr/share/icons/hicolor/32x32/animations/softwarecenter-loading-installed.gif"

    # need to include application-request-action here also since we are multiple-inheriting
    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
                    'application-request-action' : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, str),
                                       ),
                    }


    def __init__(self, db, distro, icons, cache, history, datadir):
        AppDetailsViewBase.__init__(self, db, distro, icons, cache, history, datadir)
        gtk.Viewport.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)

        self.section = None

        # atk
        self.a11y = self.get_accessible()
        self.a11y.set_name("app_details pane")

        # aptdaemon
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)

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
        self._overlay = gtk.gdk.pixbuf_new_from_file(self.INSTALLED_ICON)

        # page elements are packed into our very own lovely viewport
        self._layout_page()
        self.connect('size-allocate', self._on_allocate)
        self.vbox.connect('expose-event', self._on_expose)
        #self.app_info.image.connect_after('expose-event', self._on_icon_expose)
        return

    def _on_allocate(self, widget, allocation):
        w = allocation.width
        l = self.app_info.label.get_layout()
        if l.get_pixel_extents()[1][2] > w-84-4*mkit.EM:
            self.app_info.label.set_size_request(w-84-4*mkit.EM, -1)
        else:
            self.app_info.label.set_size_request(-1, -1)

        for p in self.app_desc.paragraphs:
            p.set_size_request(w-5*mkit.EM-166, -1)
            
        for pt in self.app_desc.points:
            pt.set_size_request(w-7*mkit.EM-166, -1)

        self.version_info.set_width(w-6*mkit.EM)
        self.license_info.set_width(w-6*mkit.EM)
        self.support_info.set_width(w-6*mkit.EM)

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
        if self.app_info.image.get_storage_type() == gtk.IMAGE_PIXBUF:
            pb = self.app_info.image.get_pixbuf()
            if pb.get_width() < 64 or pb.get_height() < 64:
                # draw icon frame
                self._draw_icon_frame(cr)
        else:
            # draw icon frame as well...
            self._draw_icon_frame(cr)

        if self.action_bar.get_property('visible'):
            self.action_bar.draw(cr,
                                 self.action_bar.allocation,
                                 event.area)
        
        if self.addons_bar.get_property('visible'):
            self.addons_bar.draw(cr,
                                 self.addons_bar.allocation,
                                 event.area)

        if self.screenshot.get_property('visible'):
            self.screenshot.draw(cr, self.screenshot.allocation, expose_area)

        if self.homepage_btn.get_property('visible'):
            self.homepage_btn.draw(cr, self.homepage_btn.allocation, expose_area)
        if self._gwibber_is_available:
            self.share_btn.draw(cr, self.share_btn.allocation, expose_area)
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
        self.vbox.set_border_width(mkit.BORDER_WIDTH_XLARGE)
        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox.set_redraw_on_allocate(False)

        # framed section that contains all app details
        self.app_info = mkit.FramedSection()
        self.app_info.image.set_size_request(84, 84)
        self.app_info.set_spacing(mkit.SPACING_LARGE)
        self.app_info.header.set_spacing(mkit.SPACING_XLARGE)
        self.app_info.header_alignment.set_padding(mkit.SPACING_SMALL,
                                                   mkit.SPACING_SMALL,
                                                   0, 0)

        self.app_info.body.set_spacing(mkit.SPACING_MED)
        self.vbox.pack_start(self.app_info, False)

        # a11y for name/summary
        self.app_info.header.set_property("can-focus", True)
        self.app_info.header.a11y = self.app_info.header.get_accessible()

        # controls which are displayed if the app is installed
        self.action_bar = PackageStatusBar(self)
        self.app_info.body.pack_start(self.action_bar, False)

        # the location of the app (if its installed)
        self.desc_installed_where = gtk.HBox(spacing=mkit.SPACING_MED)
        self.app_info.body.pack_start(self.desc_installed_where)

        # FramedSection which contains the app description
        self.desc_section = mkit.FramedSection(xpadding=mkit.SPACING_XLARGE)
        self.desc_section.header_alignment.set_padding(0,0,0,0)

        self.app_info.body.pack_start(self.desc_section, False)

        app_desc_hb = gtk.HBox(spacing=mkit.SPACING_LARGE)
        self.desc_section.body.pack_start(app_desc_hb)

        # application description wigdets
        self.app_desc = AppDescription()
        app_desc_hb.pack_start(self.app_desc, False)

        # a11y for description
        self.app_desc.body.set_property("can-focus", True)
        self.app_desc.body.a11y = self.app_desc.body.get_accessible()

        # screenshot
        self.screenshot = ScreenshotView(self.distro, self.icons)
        app_desc_hb.pack_end(self.screenshot)

        # homepage link button
        self.homepage_btn = mkit.HLinkButton(_('Website'))
        self.homepage_btn.connect('clicked', self._on_homepage_clicked)
        self.homepage_btn.set_underline(True)
        self.homepage_btn.set_xmargin(0)
        self.app_desc.footer.pack_start(self.homepage_btn, False)

        # share app with microbloggers button
        self.share_btn = mkit.HLinkButton(_('Share...'))
        self.share_btn.set_underline(True)
        self.share_btn.set_xmargin(0)
        self.share_btn.set_tooltip_text(_('Share via a micro-blogging service...'))
        self.share_btn.connect('clicked', self._on_share_clicked)
        self.app_desc.footer.pack_start(self.share_btn, False)

        alignment = gtk.Alignment()
        alignment.set_padding(mkit.SPACING_LARGE, 0, 0, 0)
        self.desc_section.body.pack_start(alignment, False)
        
        # add-on handling
        self.addon_view = self.addons_manager.table
        alignment.add(self.addon_view)

        # package info
        self.info_keys = []

        self.totalsize_info = PackageInfo(_("Total size:"), self.info_keys)
        self.app_info.body.pack_start(self.totalsize_info, False)
        
        self.addons_bar = self.addons_manager.status_bar
        self.app_info.body.pack_start(self.addons_bar, False)

        self.version_info = PackageInfo(_("Version:"), self.info_keys)
        self.app_info.body.pack_start(self.version_info, False)

        self.license_info = PackageInfo(_("License:"), self.info_keys)
        self.app_info.body.pack_start(self.license_info, False)

        self.support_info = PackageInfo(_("Updates:"), self.info_keys)
        self.app_info.body.pack_start(self.support_info, False)

        self.show_all()
        return

    def _update_page(self, app_details):

        # make title font size fixed as they should look good compared to the 
        # icon (also fixed).
        big = 20*pango.SCALE
        small = 9*pango.SCALE
        appname = gobject.markup_escape_text(app_details.display_name)

        markup = '<b><span size="%s">%s</span></b>\n<span size="%s">%s</span>'
        if app_details.pkg_state == PKG_STATE_NOT_FOUND:
            summary = app_details._error_not_found
        else:
            summary = app_details.display_summary
        if not summary:
            summary = ""
        markup = markup % (big, appname, small, gobject.markup_escape_text(summary))

        # set app- icon, name and summary in the header
        self.app_info.set_label(markup=markup)

        # a11y for name/summary
        self.app_info.header.a11y.set_name("Application: " + appname + ". Summary: " + summary)
        self.app_info.header.a11y.set_role(atk.ROLE_PANEL)
        self.app_info.header.grab_focus()

        pb = self._get_icon_as_pixbuf(app_details)
        # should we show the green tick?
        self._show_overlay = app_details.pkg_state == PKG_STATE_INSTALLED
        self.app_info.set_icon_from_pixbuf(pb)

        # if we have an error or if we need to enable a source, then hide everything else
        if app_details.pkg_state in (PKG_STATE_NOT_FOUND, PKG_STATE_NEEDS_SOURCE):
            self.screenshot.hide()
            self.version_info.hide()
            self.license_info.hide()
            self.support_info.hide()
            self.totalsize_info.hide()
            self.desc_section.hide()
        else:
            self.desc_section.show()
            self.version_info.show()
            self.license_info.show()
            self.support_info.show()
            self.totalsize_info.show()
            self.screenshot.show()

        # depending on pkg install state set action labels
        self.action_bar.configure(app_details, app_details.pkg_state)

        # format new app description
        if app_details.pkg_state == PKG_STATE_ERROR:
            description = app_details.error
        else:
            description = app_details.description
        if not description:
            description = " "
        self.app_desc.set_description(description, appname)
        # a11y for description
        self.app_desc.body.a11y.set_name("Description: " + description)

        # show or hide the homepage button and set uri if homepage specified
        if app_details.website:
            self.homepage_btn.show()
            self.homepage_btn.set_tooltip_text(app_details.website)
        else:
            self.homepage_btn.hide()

        # check if gwibber-poster is available, if so display Share... btn
        if self._gwibber_is_available:
            self.share_btn.show()
        else:
            self.share_btn.hide()

        # get screenshot urls and configure the ScreenshotView...
        if app_details.thumbnail and app_details.screenshot and not self._same_app:
            self.screenshot.configure(app_details)

            # then begin screenshot download and display sequence
            self.screenshot.download_and_display()

        # show where it is
        self._configure_where_is_it()

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

        # refresh addons interface
        self.addon_view.hide_all()
        if not app_details.error:
            gobject.idle_add(self.addons_manager.configure,
                             self.app_details.pkgname)
        
        # Update total size label
        gobject.idle_add(self.update_totalsize, True)
        
        # Update addons state bar
        self.addons_bar.configure()
        return

    def _configure_where_is_it(self):
        # remove old content
        self.desc_installed_where.foreach(lambda c: c.destroy())
        # see if we have the location if its installed
        if self.app_details.pkg_state == PKG_STATE_INSTALLED:
            searcher = GMenuSearcher()
            where = searcher.get_main_menu_path(self.app_details.desktop_file)
            if not where:
                return
            label = gtk.Label(_("Find it in the menu: "))
            self.desc_installed_where.pack_start(label, False, False)
            for (i, item) in enumerate(where):
                iconname = item.get_icon()
                if iconname and self.icons.has_icon(iconname) and i > 0:
                    image = gtk.Image()
                    image.set_from_icon_name(iconname, gtk.ICON_SIZE_SMALL_TOOLBAR)
                    self.desc_installed_where.pack_start(image, False, False)

                label_name = gtk.Label()
                label_name.set_text(item.get_name())
                self.desc_installed_where.pack_start(label_name, False, False)
                if i+1 < len(where):
                    right_arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE)
                    self.desc_installed_where.pack_start(right_arrow, 
                                                         False, False)
            self.desc_installed_where.show_all()

    # public API
    # FIXME:  port to AppDetailsViewBase as
    #         AppDetailsViewBase.show_app(self, app)
    def show_app(self, app):
        LOG.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            LOG.debug("no app selected")
            return
        
        # set button sensitive again
        self.action_bar.button.set_sensitive(True)

        # reset view to top left
        self.get_vadjustment().set_value(0)
        self.get_hadjustment().set_value(0)

        # init data
        self._same_app = (self.app and self.app.pkgname and self.app.pkgname == app.pkgname)
        self.app = app
        self.app_details = app.get_details(self.db)
        # for compat with the base class
        self.appdetails = self.app_details
        #print "AppDetailsViewGtk:"
        #print self.appdetails
        self._update_page(self.app_details)
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
        self.action_bar.button.set_sensitive(True)
        self.action_bar.button.show()
        self.addons_bar.button_apply.set_sensitive(True)
        self.addons_bar.button_cancel.set_sensitive(True)

        self.addons_bar.configure()

        if self.addons_bar.applying:
            self.addons_bar.applying = False
            
            for widget in self.addon_view:
                if widget != self.addon_view.label:
                    addon = widget.app.pkgname
                    widget.set_active(self.cache[addon].installed != None)
            return False
        
        state = self.action_bar.pkg_state
        # handle purchase: install purchased has multiple steps
        if (state == PKG_STATE_INSTALLING_PURCHASED and 
            result and
            not result.pkgname):
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLING_PURCHASED)
        elif (state == PKG_STATE_INSTALLING_PURCHASED and 
              result and
              result.pkgname):
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLED)
        # normal states
        elif state == PKG_STATE_REMOVING:
            self.action_bar.configure(self.app_details, PKG_STATE_UNINSTALLED)
        elif state == PKG_STATE_INSTALLING:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLED)
        elif state == PKG_STATE_UPGRADING:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLED)
        return False


    def _on_transaction_started(self, backend):
        self.action_bar.button.hide()
        
        if self.addons_bar.get_applying():
            self.action_bar.configure(self.app_details, APP_ACTION_APPLY)
            return
        
        state = self.action_bar.pkg_state
        LOG.debug("_on_transaction_stated %s" % state)
        if state == PKG_STATE_NEEDS_PURCHASE:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLING_PURCHASED)
        elif state == PKG_STATE_UNINSTALLED:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLING)
        elif state == PKG_STATE_INSTALLED:
            self.action_bar.configure(self.app_details, PKG_STATE_REMOVING)
        elif state == PKG_STATE_UPGRADABLE:
            self.action_bar.configure(self.app_details, PKG_STATE_UPGRADING)
        elif state == PKG_STATE_REINSTALLABLE:
            self.action_bar.configure(self.app_details, PKG_STATE_INSTALLING)
            # FIXME: is there a way to tell if we are installing/removing?
            # we will assume that it is being installed, but this means that during removals we get the text "Installing.."
            # self.action_bar.configure(self.app_details, PKG_STATE_REMOVING)
        return

    def _on_transaction_stopped(self, backend, result):
        self.action_bar.progress.hide()
        self._update_interface_on_trans_ended(result)
        return

    def _on_transaction_finished(self, backend, result):
        self.action_bar.progress.hide()
        self._update_interface_on_trans_ended(result)
        return

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if self.app_details and self.app_details.pkgname and self.app_details.pkgname == pkgname:
            if not self.action_bar.progress.get_property('visible'):
                gobject.idle_add(self._show_prog_idle_cb)
            if pkgname in backend.pending_transactions:
                self.action_bar.progress.set_fraction(progress/100.0)
            if progress == 100:
                self.action_bar.progress.set_fraction(1)
        return

    def _show_prog_idle_cb(self):
        # without using an idle callback, the progressbar suffers from
        # gitter as it gets allocated on show().  This approach either eliminates
        # the issue or makes it unnoticeable... 
        self.action_bar.progress.show()
        return False

    #def _draw_icon_inset_frame(self, cr):
        ## draw small or no icon background
        #a = self.app_info.image.allocation

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
        #line_width = max(1, int(mkit.EM*0.05+0.5))
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

    def _draw_icon_frame(self, cr):
        # draw small or no icon background
        a = self.app_info.image.allocation
        rr = mkit.ShapeRoundedRectangle()

        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)

        #rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=3)
        #cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.base[0]))
        # line width should be 0.05em but for the sake of simplicity
        # make it 0.25 pixels

        r,g,b = mkit.floats_from_gdkcolor(self.style.mid[self.state])
        rr.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=3)
        cr.set_source_rgb(r, g, b)   # for strong corners
        cr.stroke()

        cr.restore()
        return
        
    def _get_icon_as_pixbuf(self, app_details):
        icon = None
        if app_details.icon:
            if self.icons.has_icon(app_details.icon):
                try:
                    return self.icons.load_icon(app_details.icon, 84, 0)
                except glib.GError, e:
                    logging.warn("failed to load '%s'" % app_details.icon)
                    return self.icons.load_icon(MISSING_APP_ICON, 84, 0)
            elif app_details.icon_needs_download:
                self._logger.debug("did not find the icon locally, must download it")

                def on_image_download_complete(downloader, image_file_path):
                    # when the download is complete, replace the icon in the view with the downloaded one
                    pb = gtk.gdk.pixbuf_new_from_file(image_file_path)
                    self.app_info.set_icon_from_pixbuf(pb)
                    
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
            label_string += _("%sB to download, " % (download_size))
        if total_install_size > 0:
            install_size = apt_pkg.size_to_str(total_install_size)
            label_string += _("%sB when installed" % (install_size))
        elif (total_install_size == 0 and
              self.app_details.pkg_state == PKG_STATE_INSTALLED and
              not self.addons_manager.addons_to_install and
              not self.addons_manager.addons_to_remove):
            pkg = self.cache[self.app_details.pkgname].installed
            install_size = apt_pkg.size_to_str(pkg.installed_size)
            # FIXME: this is not really a good indication of the size on disk
            label_string += _("%sB on disk" % (install_size))
        elif total_install_size < 0:
            remove_size = apt_pkg.size_to_str(-total_install_size)
            label_string += _("%sB to be freed" % (remove_size))
        
        if label_string == "":
            self.totalsize_info.hide_all()
        else:
            self.totalsize_info.set_value(label_string)
            self.totalsize_info.show_all()
        return False

    def set_section(self, section):
        self.section = section
        return



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
    win.set_size_request(600,400)
    win.show_all()

    #view._config_file_prompt(None, "/etc/fstab", "/tmp/lala")

    gtk.main()
