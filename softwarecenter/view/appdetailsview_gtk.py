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
import gettext
import gio
import glib
import gmenu
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
import pangocairo

from gettext import gettext as _
import apt_pkg
from softwarecenter.backend import get_install_backend
from softwarecenter.db.application import AppDetails, Application
from softwarecenter.backend.zeitgeist_simple import zeitgeist_singleton
from softwarecenter.enums import *
from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR
from softwarecenter.utils import SimpleFileDownloader, GMenuSearcher, uri_to_filename, is_unity_running
from softwarecenter.gwibber_helper import GWIBBER_SERVICE_AVAILABLE

from appdetailsview import AppDetailsViewBase
#from actions import get_install_actions

from widgets import mkit
from widgets.description import AppDescription, TextBlock
from widgets.thumbnail import ScreenshotThumbnail
from softwarecenter.distro import get_distro

#from widgets.imagedialog import ShowImageDialog, GnomeProxyURLopener, Url404Error, Url403Error
from softwarecenter.drawing import color_floats, rounded_rect2, rounded_rect


if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

# default socket timeout to deal with unreachable screenshot site
DEFAULT_SOCKET_TIMEOUT=4

LOG = logging.getLogger("softwarecenter.view.appdetailsview")



class PackageUsageCounter(gtk.Label):

    def __init__(self, view):
        gtk.Label.__init__(self)
        self.set_alignment(0,0)
        self.set_padding(4, 0)
        self.view = view
        self.shape = mkit.ShapeRoundedRectangle()
        return

    def set_text(self, text):
        m = '<span bgcolor="darkgray" fgcolor="white"><b><small>%s</small></b></span>' % text
        gtk.Label.set_markup(self, m)
        return


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
        if not self.get_property('visible'): return
        if mkit.not_overlapping(a, expose_area): return

        cr.save()
        if self.view.section:
            r,g,b = self.view.section._section_color
        else:
            r,g,b = 0.5,0.5,0.5

        cr.rectangle(a)
        cr.set_source_rgba(r,g,b,0.333)
        cr.fill()

        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        cr.rectangle(a.x, a.y, a.width-1, a.height-1)
        cr.set_source_rgba(r,g,b,0.5)
        cr.stroke()
        cr.restore()
        return


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
            self.show_all()
    
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

        self.fill_color = COLOR_GREEN_FILL
        self.line_color = COLOR_GREEN_OUTLINE

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
        k.set_alignment(1, 0)

        # determine max width of all keys
        max_lw = 0

        for key in self.info_keys:
            l = self.create_pango_layout("")
            l.set_markup(key_markup % (dark, key))
            max_lw = max(max_lw, l.get_pixel_extents()[1][2])
            del l

        k.set_size_request(max_lw+12, -1)
        self.pack_start(k, False)

        # value
        v = self.value_label
        v.set_line_wrap(True)
        v.set_selectable(True)
        v.set_alignment(0, 0.5)
        self.pack_start(v, False)

        # a11y
        kacc = k.get_accessible()
        vacc = v.get_accessible()
        kacc.add_relationship(atk.RELATION_LABEL_FOR, vacc)
        vacc.add_relationship(atk.RELATION_LABELLED_BY, kacc)

        self.set_property("can-focus", True)
        self.show_all()

        self.connect('size-allocate', self._on_allocate,
                     v, max_lw+24+self.get_spacing())
        return

    def _on_allocate(self, widget, allocation, value_label, space_consumed):
        value_label.set_size_request(max(10, allocation.width-space_consumed), -1)
        return

    def set_width(self, width):
        if self.get_children():
            k, v = self.get_children()
            l = v.get_children()[0]
            l.set_size_request(width-k.allocation.width-self.get_spacing(), -1)
        return

    def set_value(self, value):
        self.value_label.set_markup(value)
        self.a11y.set_name(self.key + ' ' + value)


class Addon(gtk.HBox):
    """ Widget to select addons: CheckButton - Icon - Title (pkgname) """
    
    def __init__(self, db, icons, pkgname):
        gtk.HBox.__init__(self, spacing=6)

        # data
        self.app = Application("", pkgname)
        self.app_details = self.app.get_details(db)

        # checkbutton
        self.checkbutton = gtk.CheckButton()
        self.checkbutton.pkgname = self.app.pkgname
        self.pack_start(self.checkbutton, False, padding=12)

        self.connect('realize', self._on_realize, icons, pkgname)
        return

    def _on_realize(self, widget, icons, pkgname):
        # icon
        hbox = gtk.HBox(spacing=6)
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

        m = ' <span color="%s"> (%s)</span>'
        pkgname = m%(self.style.dark[0].to_string(), pkgname)

        self.title = gtk.Label()
        self.title.set_markup(title+pkgname)
        self.title.set_line_wrap(True)
        hbox.pack_start(self.title)

        self.checkbutton.add(hbox)

        self.connect('size-allocate', self._on_allocate, self.title)

        # a11y
        self.a11y = self.checkbutton.get_accessible()
        self.a11y.set_name(_("Add-on") + ': ' + title + '(' + pkgname + ')')

        self.show_all()

    def _on_allocate(self, widget, allocation, title):
#        print 'AddonWidth:', allocation.width
        width = self.allocation.width-title.allocation.x
        title.set_size_request(width, -1)
        return

    def get_active(self):
        return self.checkbutton.get_active()

    def set_active(self, is_active):
        self.checkbutton.set_active(is_active)    


class AddonsTable(gtk.VBox):
    """ Widget to display a table of addons. """
    
    def __init__(self, addons_manager):
        gtk.VBox.__init__(self, False, 12)
        self.set_resize_mode(gtk.RESIZE_QUEUE)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache
        self.db = self.addons_manager.view.db
        self.icons = self.addons_manager.view.icons
        self.recommended_addons = None
        self.suggested_addons = None
#        self.connect("realize", self._on_realize)

        self.label = mkit.EtchedLabel()
        self.label.set_alignment(0, 0.5)
        self.label.set_padding(6, 6)
        markup = _('Add-ons')
        self.label.set_markup(markup)
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
    APP_ICON_SIZE = 84 # gtk.ICON_SIZE_DIALOG ?

    # need to include application-request-action here also since we are multiple-inheriting
    __gsignals__ = {'selected':(gobject.SIGNAL_RUN_FIRST,
                                gobject.TYPE_NONE,
                                (gobject.TYPE_PYOBJECT,)),
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
        self.adjustment_value = None
        self._prev_width = 0

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
        self._overlay = gtk.gdk.pixbuf_new_from_file(INSTALLED_ICON)

        # page elements are packed into our very own lovely viewport
        self._layout_page()

        self.connect('realize', self._on_realize)
        return

    def _on_realize(self, widget):
        self.addons_bar.hide_all()
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

    def _on_expose(self, widget, event):
        a = widget.allocation

        cr = widget.window.cairo_create()
        cr.rectangle(a.x-5, a.y, a.width+10, a.height)
        cr.clip()

        color = color_floats(widget.style.light[0])

        cr.rectangle(widget.allocation)
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: self.section.render(cr, a)

        # only draw shadows when viewport is sufficiently wide...
        if a.width >= 900:
            # shadow on the right side
            lin = cairo.LinearGradient(a.x+a.width, a.y, a.x+a.width+5, a.y)
            lin.add_color_stop_rgba(0, 0,0,0, 0.175)
            lin.add_color_stop_rgba(1, 0,0,0, 0.000)

            cr.rectangle(a.x+a.width, a.y, 5, a.height)
            cr.set_source(lin)
            cr.fill()

            cr.set_line_width(1)

            # right side
            # outer vertical strong line
            cr.move_to(a.x+a.width+0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
            cr.stroke()

            # inner vertical highlight
            cr.move_to(a.x+a.width-0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgba(1,1,1,0.3)
            cr.stroke()

            # shadow on the left side
            lin = cairo.LinearGradient(a.x-5, a.y, a.x, a.y)
            lin.add_color_stop_rgba(1, 0,0,0, 0.175)
            lin.add_color_stop_rgba(0, 0,0,0, 0.000)

            cr.rectangle(a.x-5, a.y, 5, a.height)
            cr.set_source(lin)
            cr.fill()

            # left side
            # outer vertical strong line
            cr.move_to(a.x-0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
            cr.stroke()

            # inner vertical highlight
            cr.move_to(a.x+0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgba(1,1,1,0.3)
            cr.stroke()


        # draw the info vbox bg
        a = self.info_vb.allocation
        rounded_rect(cr, a.x, a.y, a.width, a.height, 5)
        cr.set_source_rgba(*color_floats("#F7F7F7")+(0.75,))
        cr.fill()

        # draw the info header bg
        a = self.addon_view.label.allocation
        # hack: the > 200 is so we dont get premature drawing of the add-ons bg
        if self.addon_view.get_property("visible") and a.y > 200:
            rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))
            cr.set_source_rgb(*color_floats("#DAD7D3"))
            cr.fill()

        # draw the info header bg
        if self.addon_view.get_property("visible"):
            cr.rectangle(self.info_header.allocation)
        else:
            a = self.info_header.allocation
            rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))

        cr.set_source_rgb(*color_floats("#DAD7D3"))
        cr.fill()

        a = self.info_vb.allocation
        cr.save()
        rounded_rect(cr, a.x+0.5, a.y+0.5, a.width-1, a.height-1, 5)
        cr.set_source_rgba(*color_floats("#DAD7D3")+(0.3,))
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

        # draw subwidgets
        self.action_bar.draw(cr, self.action_bar.allocation, event.area)
        self.screenshot.draw(cr, self.screenshot.allocation, event.area)
        self.addons_bar.draw(cr, self.addons_bar.allocation, event.area)

        del cr
        return

    def _on_allocate(self, viewport, allocation, vbox):
        gobject.idle_add(self.queue_draw)

        w = min(allocation.width-2, 900)

        if w <= 400 or w == self._prev_width: return True
        self._prev_width = w

        vbox.set_size_request(w, -1)
        return True

    def _on_key_press(self, widget, event):
        kv = gtk.keysyms
        if event.keyval == kv.BackSpace:
            self.back.emit('clicked')
        return

    def _on_key_release(self, widget, event, entry):
        ctrl = event.state & gtk.gdk.CONTROL_MASK
        if ctrl:
            if event.keyval == gtk.keysyms.s:
                entry.set_position(-1)
                entry.grab_focus()
        return

    def _layout_page(self):
        # setup widgets
        a = gtk.Alignment(0.5, 0.0, yscale=1.0)
        self.add(a)

        self.hbox = gtk.HBox()
        a.add(self.hbox)

        vb = gtk.VBox(spacing=18)
        vb.set_border_width(20)
        vb.set_redraw_on_allocate(False)
        self.set_redraw_on_allocate(False)
        self.hbox.pack_start(vb, False)

        # header
        hb = gtk.HBox(spacing=12)
        vb.pack_start(hb)

        # the app icon
        self.icon = gtk.Image()
        self.icon.set_size_request(84,-1)
        self.icon.set_from_icon_name(MISSING_APP_ICON, gtk.ICON_SIZE_DIALOG)
        hb.pack_start(self.icon, False)

        # the app title/summary
        self.title = mkit.EtchedLabel('<span font_desc="bold 20">Title</span>\nSummary')
        self.title.set_alignment(0, 0.5)
        vb_inner=gtk.VBox(spacing=6)
        vb_inner.pack_start(self.title, False)

        # if zeitgeist is installed,
        # the amount of times it was used
        self.usage = PackageUsageCounter(self)
        vb_inner.pack_start(self.usage, False)
        hb.pack_start(vb_inner)

        # the package status bar
        self.action_bar = PackageStatusBar(self)
        vb.pack_start(self.action_bar, False)

        # the hbox that hold the description on the left and the screenshot 
        # thumbnail on the right
        body_hb = gtk.HBox(spacing=12)
        vb.pack_start(body_hb, False)

        # append the description widget, hold the formatted long description
        self.desc = AppDescription(viewport=self)
        body_hb.pack_start(self.desc)

        # the thumbnail/screenshot
        self.screenshot = ScreenshotThumbnail(get_distro(), self.icons)
        body_hb.pack_start(self.screenshot, False)

        # homepage link button
        self.homepage_btn = mkit.HLinkButton(_('Website'))
        self.homepage_btn.connect('clicked', self._on_homepage_clicked)
        self.homepage_btn.set_underline(True)
        self.homepage_btn.set_xmargin(0)

        # share app with microbloggers button
        self.share_btn = mkit.HLinkButton(_('Share...'))
        self.share_btn.set_underline(True)
        self.share_btn.set_xmargin(0)
        self.share_btn.set_tooltip_text(_('Share via a micro-blogging service...'))
        self.share_btn.connect('clicked', self._on_share_clicked)

        # add the links footer to the description widget
        footer_hb = gtk.HBox(spacing=6)
        footer_hb.pack_start(self.homepage_btn, False)
        footer_hb.pack_start(self.share_btn, False)
        self.desc.pack_start(footer_hb, False)

#        # a11y for name/summary
#        self.app_info.header.set_property("can-focus", True)
#        self.app_info.header.a11y = self.app_info.header.get_accessible()

#        # the location of the app (if its installed)
#        self.desc_installed_where = gtk.HBox(spacing=mkit.SPACING_MED)
#        self.app_info.body.pack_start(self.desc_installed_where)
#        self.desc_installed_where.a11y = self.desc_installed_where.get_accessible()

#        # a11y for description
#        self.app_desc.description.set_property("can-focus", True)
#        self.app_desc.description.a11y = self.app_desc.description.get_accessible()

        self.info_vb = info_vb = gtk.VBox(spacing=12)
        vb.pack_start(info_vb, False)

        # add-on handling
        self.addon_view = self.addons_manager.table
        info_vb.pack_start(self.addon_view, False)

        self.addons_bar = self.addons_manager.status_bar
        info_vb.pack_start(self.addons_bar, False)

        # package info
        self.info_keys = []

        # info header
        self.info_header = mkit.EtchedLabel("Details")
        self.info_header.set_alignment(0, 0.5)
        self.info_header.set_padding(6, 6)
        self.info_header.set_use_markup(True)
        info_vb.pack_start(self.info_header, False)

        self.totalsize_info = PackageInfo(_("Total size:"), self.info_keys)
        info_vb.pack_start(self.totalsize_info, False)

        self.version_info = PackageInfo(_("Version:"), self.info_keys)
        info_vb.pack_start(self.version_info, False)

        self.license_info = PackageInfo(_("License:"), self.info_keys)
        info_vb.pack_start(self.license_info, False)

        self.support_info = PackageInfo(_("Updates:"), self.info_keys)
        info_vb.pack_start(self.support_info, False)

        padding = gtk.VBox()
        padding.set_size_request(-1, 6)
        info_vb.pack_end(padding, False)

        self.show_all()

        # signals!
        self.connect('key-press-event', self._on_key_press)
#        self.connect('key-release-event', self._on_key_release, entry)
        vb.connect('expose-event', self._on_expose)
        self.connect('size-allocate', self._on_allocate, vb)
        return

    def _update_title_markup(self, appname, summary):
        # make title font size fixed as they should look good compared to the 
        # icon (also fixed).
        markup = '<span font_desc="bold 20">%s</span>\n<span font_desc="9">%s</span>'
        markup = markup % (appname, gobject.markup_escape_text(summary))

        self.title.set_markup(markup)

#        # a11y for name/summary
#        self.app_info.header.a11y.set_name("Application: " + appname + ". Summary: " + summary)
#        self.app_info.header.a11y.set_role(atk.ROLE_PANEL)
#        self.app_info.header.grab_focus()
        return

    def _update_app_icon(self, app_details):
        pb = self._get_icon_as_pixbuf(app_details)
        # should we show the green tick?
#        self._show_overlay = app_details.pkg_state == PKG_STATE_INSTALLED
        self.icon.set_from_pixbuf(pb)
        return

    def _update_layout_error_status(self, pkg_error):
        # if we have an error or if we need to enable a source, then hide everything else
        if pkg_error:
            self.screenshot.hide()
            self.version_info.hide()
            self.license_info.hide()
            self.support_info.hide()
            self.totalsize_info.hide()
        else:
            self.version_info.show()
            self.license_info.show()
            self.support_info.show()
            self.totalsize_info.show()
            self.screenshot.show()
        return

    def _update_app_description(self, app_details, pkgname):
        # format new app description
        if app_details.pkg_state == PKG_STATE_ERROR:
            description = app_details.error
        else:
            description = app_details.description
        if not description:
            description = " "
        self.desc.set_description(description, pkgname)
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

            # inititate the download and display series of callbacks
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
        self.addon_view.hide_all()

        if not app_details.error:
            self.addons_manager.configure(self.app_details.pkgname)

        # Update total size label
        self.totalsize_info.set_value(_("Calculating..."))
        gobject.timeout_add(500, self.update_totalsize, True)
        
        # Update addons state bar
        self.addons_bar.configure()
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

        # depending on pkg install state set action labels
        self.action_bar.configure(app_details, app_details.pkg_state)

        self._update_title_markup(appname, summary)
        self._update_app_icon(app_details)
        self._update_layout_error_status(pkg_ambiguous_error)
        self._update_app_description(app_details, appname)
        self._update_description_footer_links(app_details)
        self._update_app_screenshot(app_details)
        self._update_pkg_info_table(app_details)
        self._update_addons(app_details)
        self._update_usage_counter()

#        # show where it is
#        self._configure_where_is_it()
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
#        self._update_layout_error_status(pkg_ambiguous_error)
        self._update_app_description(app_details, app_details.pkgname)
        self._update_app_screenshot(app_details)
        self._update_description_footer_links(app_details)
        self._update_pkg_info_table(app_details)
        gobject.timeout_add(500, self._update_addons, app_details)

        # depending on pkg install state set action labels
        self.action_bar.configure(app_details, app_details.pkg_state)

#        # show where it is
#        self._configure_where_is_it()
        return

    def _configure_where_is_it(self):
        # disable where-is-it under Unity as it does not apply there
        if is_unity_running():
            return
        # remove old content
        self.desc_installed_where.foreach(lambda c: c.destroy())
        self.desc_installed_where.set_property("can-focus", False)
        self.desc_installed_where.a11y.set_name('')
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
            self.desc_installed_where.pack_start(label, False, False)
            for (i, item) in enumerate(where):
                iconname = item.get_icon()
                # check icontheme first
                if iconname and self.icons.has_icon(iconname) and i > 0:
                    image = gtk.Image()
                    image.set_from_icon_name(iconname, gtk.ICON_SIZE_SMALL_TOOLBAR)
                    self.desc_installed_where.pack_start(image, False, False)
                # then see if its a path to a file on disk
                elif iconname and os.path.exists(iconname):
                    image = gtk.Image()
                    pb = gtk.gdk.pixbuf_new_from_file_at_size(iconname, 18, 18)
                    if pb:
                        image.set_from_pixbuf(pb)
                    self.desc_installed_where.pack_start(image, False, False)

                label_name = gtk.Label()
                if item.get_type() == gmenu.TYPE_ENTRY:
                    label_name.set_text(item.get_display_name())
                else:
                    label_name.set_text(item.get_name())
                self.desc_installed_where.pack_start(label_name, False, False)
                if i+1 < len(where):
                    right_arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_NONE)
                    self.desc_installed_where.pack_start(right_arrow, 
                                                         False, False)

            # create our a11y text
            a11y_text = ""
            for widget in self.desc_installed_where:
                if isinstance(widget, gtk.Label):
                    a11y_text += ' > ' + widget.get_text()
            self.desc_installed_where.a11y.set_name(a11y_text)
            self.desc_installed_where.set_property("can-focus", True)

            self.desc_installed_where.show_all()

    # public API
    # FIXME:  port to AppDetailsViewBase as
    #         AppDetailsViewBase.show_app(self, app)
    def show_app(self, app):
        LOG.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            LOG.debug("no app selected")
            return

        # reset view to top left
        self.get_vadjustment().set_value(0)
        self.get_hadjustment().set_value(0)

#        # set button sensitive again
        self.action_bar.button.set_sensitive(True)

        # init data
        old_details = self.app_details
        self.app = app
        self.app_details = app.get_details(self.db)
        self._same_app = old_details and self.app_details.same_app(old_details)

        # for compat with the base class
        self.appdetails = self.app_details
        # stop here if its the same apph
        if self._same_app: 
            return
        # update all if not the same app
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
        self.action_bar.button.set_sensitive(True)
        self.action_bar.button.show()
        self.addons_bar.button_apply.set_sensitive(True)
        self.addons_bar.button_cancel.set_sensitive(True)
        self.addons_bar.configure()
        self.adjustment_value = None
        
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
                self.action_bar.button.hide()
                self.action_bar.progress.show()
            if pkgname in backend.pending_transactions:
                self.action_bar.progress.set_fraction(progress/100.0)
            if progress >= 100:
                self.action_bar.progress.set_fraction(1)
                self.adjustment_value = self.get_vadjustment().get_value()
        return

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
                image_downloader = SimpleFileDownloader()
                image_downloader.connect('download-complete', on_image_download_complete)
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
            pass
#            self.totalsize_info.set_value(_("Calculating..."))
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
            self.totalsize_info.set_value(_("Unknown"))
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
            self.totalsize_info.set_value(_("Unknown"))
        else:
            self.totalsize_info.set_value(label_string)
#            self.totalsize_info.show_all()
        return False

    def set_section(self, section):
        self.section = section
        return
        
    def _update_usage_counter(self):
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
            self.usage.set_text(label_string)
            self.usage.show()

        # try to get it
        zeitgeist_singleton.get_usage_counter(
            self.app_details.desktop_file, _zeitgeist_callback)


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
    win.set_size_request(600,400)
    win.show_all()

    #view._config_file_prompt(None, "/etc/fstab", "/tmp/lala")

    gtk.main()
