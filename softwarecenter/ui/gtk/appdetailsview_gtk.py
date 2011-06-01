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
import datetime
import gettext
import glib
import gmenu
import gobject
import gtk
import logging
import os
import sys


from softwarecenter.cmdfinder import CmdFinder
from softwarecenter.netstatus import NetState, get_network_watcher, network_state_is_connected

from gettext import gettext as _
import apt_pkg

from softwarecenter.db.application import Application
from softwarecenter.backend.reviews import ReviewStats

from softwarecenter.backend.zeitgeist_simple import zeitgeist_singleton
from softwarecenter.enums import (PKG_STATE_INSTALLING_PURCHASED,
                                  PKG_STATE_INSTALLED,
                                  PKG_STATE_PURCHASED_BUT_REPO_MUST_BE_ENABLED,
                                  PKG_STATE_NEEDS_PURCHASE,
                                  PKG_STATE_NEEDS_SOURCE,
                                  PKG_STATE_UNINSTALLED,
                                  PKG_STATE_REINSTALLABLE,
                                  PKG_STATE_UPGRADABLE,
                                  PKG_STATE_INSTALLING,
                                  PKG_STATE_UPGRADING,
                                  PKG_STATE_REMOVING,
                                  PKG_STATE_NOT_FOUND,
                                  PKG_STATE_UNKNOWN,
                                  APP_ACTION_APPLY,
                                  PKG_STATE_ERROR,
                                  SOFTWARE_CENTER_PKGNAME,
                                  MISSING_APP_ICON,
                                  )
from softwarecenter.utils import (is_unity_running, 
                                  get_exec_line_from_desktop,
                                  GMenuSearcher,
                                  SimpleFileDownloader,
                                  )
from softwarecenter.backend.weblive import get_weblive_backend

from dialogs import error

from appdetailsview import AppDetailsViewBase

from widgets import mkit

from widgets.mkit import EM
from widgets.reviews import (UIReviewsList, 
                             ReviewStatsContainer, 
                             StarPainter,
                             StarRating,
                             )

from widgets.description import AppDescription
from widgets.thumbnail import ScreenshotThumbnail
from widgets.weblivedialog import ShowWebLiveServerChooserDialog

from softwarecenter.distro import get_distro

from softwarecenter.drawing import alpha_composite, color_floats, rounded_rect2, rounded_rect

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")

# default socket timeout to deal with unreachable screenshot site
DEFAULT_SOCKET_TIMEOUT=4

LOG = logging.getLogger(__name__)
LOG_ALLOCATION = logging.getLogger("softwarecenter.ui.gtk.allocation")


# fixed black for action bar label, taken from Ambiance gtk-theme
COLOR_BLACK = '#323232'

class StatusBar(gtk.Alignment):

    # mid-gray: when no section color is available
    SECTION_FALLBACK_COLOR = '#808080'

    # action colours, taken from synaptic
    # red: used for pkg_status errors or serious warnings
    PKG_STATUS_ERROR_COLOR = '#FF9595'

    # yellow: some user action is required outside of install or remove
    USER_ACTION_REQRD_COLOR = '#FFC61A'


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
        self.create_colors()

        self.connect('style-set', self._on_style_set)

    def _on_style_set(self, widget, old_style):
        self.set_size_request(-1, 3*EM)
        self.create_colors()
        return

    def create_colors(self, src_color=None):
        if src_color:
            bg = color_floats(src_color)
        elif self.view.section:
            bg = self.view.section._section_color
        else:
            bg = color_floats(StatusBar.SECTION_FALLBACK_COLOR)

        self.line_color = alpha_composite(bg+(0.6,), (1,1,1))
        self.bg_color = alpha_composite(bg+(0.333,), (1,1,1))
        return

    def draw(self, cr, a, expose_area):
        if not self.get_property('visible'): return
        if mkit.not_overlapping(a, expose_area): return

        cr.save()

        cr.rectangle(a)
        cr.set_source_rgb(*self.bg_color)
        cr.fill()

        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        cr.rectangle(a.x, a.y, a.width-1, a.height-1)
        cr.set_source_rgb(*self.line_color)
        cr.stroke()
        cr.restore()
        return


class PackageStatusBar(StatusBar):
    
    def __init__(self, view):
        StatusBar.__init__(self, view)
        self.label = mkit.EtchedLabel()
        self.button = gtk.Button()
        self.progress = gtk.ProgressBar()

        # theme engine hint for bug #606942
        self.progress.set_data("transparent-bg-hint", True)

        self.pkg_state = None

        self.hbox.pack_start(self.label, False)
        self.hbox.pack_end(self.button, False)
        self.hbox.pack_end(self.progress, False)
        self.show_all()

        self.view.connect('style-set', self._on_view_style_set)
        self.button.connect('clicked', self._on_button_clicked)
        glib.timeout_add(500, self._pulse_helper)

    def _on_view_style_set(self, view, old_style):
        self._progress_modify_bg(view)
        return

    def _progress_modify_bg(self, view):
        # more in relation to bug #606942
        # for themes where "transparent-bg-hint" is not understood
        self.create_colors()
        self.progress.modify_bg(gtk.STATE_NORMAL,
                                gtk.gdk.Color(*self.bg_color))
        return

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

        self.create_colors()

        if state in (PKG_STATE_INSTALLING,
                     PKG_STATE_INSTALLING_PURCHASED,
                     PKG_STATE_REMOVING,
                     PKG_STATE_UPGRADING,
                     APP_ACTION_APPLY):
            self.show()
        elif state == PKG_STATE_NOT_FOUND:
            self.hide()
        elif state == PKG_STATE_ERROR:
            self.progress.hide()
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
            #special label only if the app being viewed is software centre itself
            if app_details.pkgname== SOFTWARE_CENTER_PKGNAME:
                self.set_label(_("Installed (you're using it right now)"))
            else:
                if app_details.purchase_date:
                    # purchase_date is a string, must first convert to datetime.datetime
                    pdate = self._convert_purchase_date_str_to_datetime(app_details.purchase_date)
                    # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31, please specify a format per your
                    # locale (if you prefer, %x can be used to provide a default locale-specific date 
                    # representation)
                    self.set_label(pdate.strftime(_('Purchased on %Y-%m-%d')))
                elif app_details.installation_date:
                    # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31, please specify a format per your
                    # locale (if you prefer, %x can be used to provide a default locale-specific date 
                    # representation)
                    template = _('Installed on %Y-%m-%d')
                    self.set_label(app_details.installation_date.strftime(template))
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
            # purchase_date is a string, must first convert to datetime.datetime
            pdate = self._convert_purchase_date_str_to_datetime(app_details.purchase_date)
            # TRANSLATORS : %Y-%m-%d formats the date as 2011-03-31, please specify a format per your
            # locale (if you prefer, %x can be used to provide a default locale-specific date 
            # representation)
            self.set_label(pdate.strftime(_('Purchased on %Y-%m-%d')))
            self.set_button_label(_('Install'))
        elif state == PKG_STATE_UNINSTALLED:
            #special label only if the app being viewed is software centre itself
            if app_details.pkgname== SOFTWARE_CENTER_PKGNAME:
                self.set_label(_("Removed (close it and it'll be gone)"))
            else:
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
            self.create_colors(StatusBar.PKG_STATUS_ERROR_COLOR)
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
            self.create_colors(StatusBar.USER_ACTION_REQRD_COLOR)
        if (self.app_details.warning and not self.app_details.error and
           not state in (PKG_STATE_INSTALLING, PKG_STATE_INSTALLING_PURCHASED,
           PKG_STATE_REMOVING, PKG_STATE_UPGRADING, APP_ACTION_APPLY)):
            self.set_label(self.app_details.warning)

        sensitive = network_state_is_connected()
        self.button.set_sensitive(sensitive)
        return
        
    def _convert_purchase_date_str_to_datetime(self, purchase_date):
        if purchase_date is not None:
            return datetime.datetime.strptime(purchase_date, "%Y-%m-%d %H:%M:%S")


class PackageInfo(gtk.HBox):

    def __init__(self, key, info_keys):
        gtk.HBox.__init__(self, spacing=mkit.SPACING_XLARGE)
        self.key = key
        self.info_keys = info_keys
        self.info_keys.append(key)
        self.value_label = gtk.Label()
        self.value_label.set_selectable(True)
        self.a11y = self.get_accessible()

        self._allocation = None

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
        if self._allocation == allocation:
            LOG_ALLOCATION.debug("PackageInfoAllocate skipped!")
            return True
        self._allocation = allocation

        LOG_ALLOCATION.debug("on_alloc widget=%s, allocation=%s" % (widget, allocation))

        value_label.set_size_request(max(10, allocation.width-space_consumed), -1)
        return True

    def set_width(self, width):
        return

    def set_value(self, value):
        self.value_label.set_markup(value)
        self.a11y.set_name(self.key + ' ' + value)

class Addon(gtk.HBox):
    """ Widget to select addons: CheckButton - Icon - Title (pkgname) """

    def __init__(self, db, icons, pkgname):
        gtk.HBox.__init__(self, spacing=mkit.SPACING_SMALL)
        self.set_border_width(2)

        # data
        self.app = Application("", pkgname)
        self.app_details = self.app.get_details(db)

        # checkbutton
        self.checkbutton = gtk.CheckButton()
        self.checkbutton.pkgname = self.app.pkgname
        self.pack_start(self.checkbutton, False, padding=12)

        self._allocation = None

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
        self.title.set_alignment(0.0, 0.5)
        self.title.set_line_wrap(True)
#        self.title.set_ellipsize(pango.ELLIPSIZE_END)
        hbox.pack_start(self.title)

        loader = self.get_ancestor(AppDetailsViewGtk).review_loader
        stats = loader.get_review_stats(self.app)
        if stats != None:
            rating = StarRating()
            hbox.pack_end(rating, False)
            rating.set_rating(stats.ratings_average)

        self.checkbutton.add(hbox)
        self.connect('size-allocate', self._on_allocate, self.title)
        self.show_all()

    def _on_allocate(self, widget, allocation, title):
        if self._allocation == allocation:
            LOG_ALLOCATION.debug("AddonAllocate skipped!")
            return True
        self._allocation = allocation

        LOG_ALLOCATION.debug("on_alloc widget=%s, allocation=%s" % (widget, allocation))
        hw = widget.allocation.width
        cw = self.checkbutton.allocation.width
        tw = title.allocation.width

        width = max(10, hw - (cw - tw) - 24)
        title.set_size_request(width, -1)
        return True

    def get_active(self):
        return self.checkbutton.get_active()

    def set_active(self, is_active):
        self.checkbutton.set_active(is_active)

    def set_width(self, width):
        return


class AddonsTable(gtk.VBox):
    """ Widget to display a table of addons. """

    __gsignals__ = {'table-built' : (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                   }

    def __init__(self, addons_manager):
        gtk.VBox.__init__(self, False, 12)
        self.addons_manager = addons_manager
        self.cache = self.addons_manager.view.cache
        self.db = self.addons_manager.view.db
        self.icons = self.addons_manager.view.icons
        self.recommended_addons = None
        self.suggested_addons = None

        self.label = mkit.EtchedLabel()
        self.label.set_alignment(0, 0.5)
        self.label.set_padding(6, 6)

        markup = _('Add-ons')
        self.label.set_markup(markup)
        self.pack_start(self.label, False, False)

    def get_addons(self):
        # filter all children widgets and return only Addons
        return filter(lambda w: isinstance(w, Addon), self)

    def clear(self):
        for addon in self.get_addons():
            addon.destroy()

    def addons_set_sensitive(self, is_sensitive):
        for addon in self.get_addons():
            addon.set_sensitive(is_sensitive)

    def set_addons(self, addons):
        self.recommended_addons = sorted(addons[0])
        self.suggested_addons = sorted(addons[1])

        if not self.recommended_addons and not self.suggested_addons:
            return

        # clear any existing addons
        self.clear()

        # set the new addons
        exists = set()
        for addon_name in self.recommended_addons + self.suggested_addons:
            if not addon_name in self.cache or addon_name in exists:
                continue

            addon = Addon(self.db, self.icons, addon_name)
            #addon.pkgname.connect("clicked", not yet suitable for use)
            addon.set_active(self.cache[addon_name].installed != None)
            addon.checkbutton.connect("toggled",
                                      self.addons_manager.mark_changes)
            self.pack_start(addon, False)
            exists.add(addon_name)
        self.show_all()

        self.emit('table-built')
        return False


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
        LOG.debug("AddonsStatusBarConfigure")
        # FIXME: addons are not always free, but the old implementation 
        #        of determining price was buggy
        if (not self.addons_manager.addons_to_install and 
            not self.addons_manager.addons_to_remove):
            self.hide_all()
        else:
            sensitive = network_state_is_connected()
            self.button_apply.set_sensitive(sensitive)
            self.button_cancel.set_sensitive(sensitive)
            self.show_all()
   
    def _on_button_apply_clicked(self, button):
        self.applying = True
        self.button_apply.set_sensitive(False)
        self.button_cancel.set_sensitive(False)
        # these two lines are the magic that make it work
        self.view.addons_to_install = self.addons_manager.addons_to_install
        self.view.addons_to_remove = self.addons_manager.addons_to_remove
        LOG.debug("ApplyButtonClicked: inst=%s rm=%s" % (
                self.view.addons_to_install, self.view.addons_to_remove))
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
        LOG.debug("mark_changes")
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
        gobject.idle_add(self.view.update_totalsize,
                         priority=glib.PRIORITY_LOW)

    def configure(self, pkgname, update_addons=True):
        self.addons_to_install = []
        self.addons_to_remove = []
        if update_addons:
            self.addons = self.view.cache.get_addons(pkgname)
            self.table.set_addons(self.addons)
        self.status_bar.configure()

        sensitive = network_state_is_connected()
        self.table.addons_set_sensitive(sensitive)

    def restore(self, *button):
        self.addons_to_install = []
        self.addons_to_remove = []
        self.configure(self.view.app.pkgname)
        gobject.idle_add(self.view.update_totalsize,
                         priority=glib.PRIORITY_LOW)


class AppDetailsViewGtk(gtk.Viewport, AppDetailsViewBase):

    """ The view that shows the application details """

    # the size of the icon on the left side
    APP_ICON_SIZE = 84 # gtk.ICON_SIZE_DIALOG ?

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


    def __init__(self, db, distro, icons, cache, datadir, pane):
        AppDetailsViewBase.__init__(self, db, distro, icons, cache, datadir)
        gtk.Viewport.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)

        self._allocation = None
        self._pane = pane

        self.section = None
        # app specific data
        self.app = None
        self.app_details = None
        self.pkg_state = None

        self.review_stats_widget = ReviewStatsContainer()
        self.reviews = UIReviewsList(self)

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

        # addons manager
        self.addons_manager = AddonsManager(self)
        self.addons_statusbar = self.addons_manager.status_bar
        self.addons_to_install = self.addons_manager.addons_to_install
        self.addons_to_remove = self.addons_manager.addons_to_remove

        # reviews
        self._reviews_server_page = 1
        self._reviews_server_language = None
        
        # switches
        self._show_overlay = False

        # page elements are packed into our very own lovely viewport
        self._layout_page()

        self.connect('realize', self._on_realize)

        self.loaded = True
        return

    def _on_net_state_changed(self, watcher, state):
        if state == NetState.NM_STATE_DISCONNECTED:
            self._check_for_reviews()
        elif state == NetState.NM_STATE_CONNECTED:
            gobject.timeout_add(500, self._check_for_reviews)

        # set addon table and action button states based on sensitivity
        sensitive = state == NetState.NM_STATE_CONNECTED
        self.pkg_statusbar.button.set_sensitive(sensitive)
        self.addon_view.addons_set_sensitive(sensitive)
        self.addons_statusbar.button_apply.set_sensitive(sensitive)
        self.addons_statusbar.button_cancel.set_sensitive(sensitive)
        return

    # FIXME: should we just this with _check_for_reviews?
    def _update_reviews(self, app_details):
        self.reviews.clear()
        self._check_for_reviews()
        return

    def _check_for_reviews(self):
        # self.app may be undefined on network state change events (LP: #742635)
        if not self.app:
            return
        # review stats is fast and syncronous
        stats = self.review_loader.get_review_stats(self.app)
        self._update_review_stats_widget(stats)
        # individual reviews is slow and async so we just queue it here
        self._do_load_reviews()

    def _on_more_reviews_clicked(self, uilist):
        self._reviews_server_page += 1
        self._do_load_reviews()

    def _on_reviews_in_different_language_clicked(self, uilist, language):
        self._reviews_server_language = language
        self._do_load_reviews()

    def _do_load_reviews(self):
        self.reviews.show_spinner_with_message(_('Checking for reviews...'))
        self.review_loader.get_reviews(
            self.app, self._reviews_ready_callback, 
            page=self._reviews_server_page,
            language=self._reviews_server_language)

    def _update_review_stats_widget(self, stats):
        if stats:
            # ensure that the review UI knows about the stats 
            self.reviews.global_review_stats = stats
            # update the widget
            self.review_stats_widget.set_avg_rating(stats.ratings_average)
            self.review_stats_widget.set_nr_reviews(stats.ratings_total)
            self.review_stats_widget.show()
        else:
            self.review_stats_widget.hide()

    def _reviews_ready_callback(self, app, reviews_data, my_votes=None):
        """ callback when new reviews are ready, cleans out the
            old ones
        """
        LOG.debug("_review_ready_callback: %s" % app)
        # avoid possible race if we already moved to a new app when
        # the reviews become ready 
        # (we only check for pkgname currently to avoid breaking on
        #  software-center totem)
        if self.app.pkgname != app.pkgname:
            return

        # update the stats (if needed). the caching can make them
        # wrong, so if the reviews we have in the list are more than the
        # stats we update manually
        old_stats = self.review_loader.get_review_stats(self.app)
        if ((old_stats is None and len(reviews_data) > 0) or
            (old_stats is not None and old_stats.ratings_total < len(reviews_data))):
            # generate new stats
            stats = ReviewStats(app)
            stats.ratings_total = len(reviews_data)
            if stats.ratings_total == 0:
                stats.ratings_average = 0
            else:
                stats.ratings_average = sum([x.rating for x in reviews_data]) / float(stats.ratings_total)
            # update UI
            self._update_review_stats_widget(stats)
            # update global stats cache as well
            self.review_loader.update_review_stats(app, stats)
        
        if my_votes:
            self.reviews.update_useful_votes(my_votes)
        
        for review in reviews_data:
            self.reviews.add_review(review)
        self.reviews.configure_reviews_ui()

    def on_weblive_progress(self, weblive, progress):
        """ When receiving connection progress, update button """
        self.test_drive.set_label(_("Connection ... (%s%%)") % (progress))

    def on_weblive_connected(self, weblive, can_disconnect):
        """ When connected, update button """
        if can_disconnect:
            self.test_drive.set_label(_("Disconnect"))
            self.test_drive.set_sensitive(True)
        else:
            self.test_drive.set_label(_("Connected"))

    def on_weblive_disconnected(self, weblive):
        """ When disconnected, reset button """
        self.test_drive.set_label(_("Test drive"))
        self.test_drive.set_sensitive(True)

    def on_weblive_exception(self, weblive, exception):
        """ When receiving an exception, reset button and show the error """
        error(None,"WebLive exception", exception)
        self.test_drive.set_label(_("Test drive"))
        self.test_drive.set_sensitive(True)

    def on_weblive_warning(self, weblive, warning):
        """ When receiving a warning, just show it """
        error(None,"WebLive warning", warning)

    def on_test_drive_clicked(self, button):
        if self.weblive.client.state == "disconnected":
            # get exec line
            exec_line = get_exec_line_from_desktop(self.desktop_file)

            # split away any arguments, gedit for example as %U
            cmd = exec_line.split()[0]

            # Get the list of servers
            servers = self.weblive.get_servers_for_pkgname(self.app.pkgname)

            if len(servers) == 0:
                error(None,"No available server", "There is currently no available WebLive server for this application.\nPlease try again later.")
            elif len(servers) == 1:
                self.weblive.create_automatic_user_and_run_session(session=cmd,serverid=servers[0].name)
                button.set_sensitive(False)
            else:
                d = ShowWebLiveServerChooserDialog(servers, self.app.pkgname)
                serverid=None
                if d.run() == gtk.RESPONSE_OK:
                    for server in d.servers_vbox:
                        if server.get_active():
                            serverid=server.serverid
                            break
                d.destroy()

                if serverid:
                    self.weblive.create_automatic_user_and_run_session(session=cmd,serverid=serverid)
                    button.set_sensitive(False)

        elif self.weblive.client.state == "connected":
            button.set_sensitive(False)
            self.weblive.client.disconnect_session()

    def _on_addon_table_built(self, table):
        if not table.parent:
            self.info_vb.pack_start(table, False)
            self.info_vb.reorder_child(table, 0)
        if not table.get_property('visible'):
            table.show_all()
        return

    def _on_expose(self, widget, event, alignment):
        cr = widget.window.cairo_create()
        cr.rectangle(alignment.allocation)
        cr.clip_preserve()

        color = color_floats(widget.style.light[gtk.STATE_NORMAL])
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: 
            self.section.render(cr, self, alignment.allocation)

        if self.info_header.get_property('visible'):
            # draw the info vbox bg
            a = self.info_vb.allocation
            rounded_rect(cr, a.x, a.y, a.width, a.height, 5)
            cr.set_source_rgba(*color_floats("#F7F7F7")+(0.75,))
            cr.fill()

        # draw the addon header bg
        a = self.addon_view.label.allocation
        if self.addon_view.parent:
            rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))
            cr.set_source_rgb(*color_floats("#DAD7D3"))
            cr.fill()

        if self.info_header.get_property('visible'):
            # draw the info header bg, shape depends on visibility of addons
            if self.addon_view.parent:
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
        self.usage.draw(cr, self.usage.allocation, event.area)
        self.pkg_statusbar.draw(cr, self.pkg_statusbar.allocation, event.area)
        if self.screenshot.get_property('visible'):
            self.screenshot.draw(cr, self.screenshot.allocation, event.area)
        self.addons_statusbar.draw(cr, self.addons_statusbar.allocation, event.area)
        self.reviews.draw(cr, self.reviews.allocation)
        del cr
        return

    def _on_allocate(self, widget, allocation):
        self.queue_draw()

        if allocation == self._allocation:
            LOG_ALLOCATION.debug("TopAllocate skipped!")
            return True

        LOG_ALLOCATION.debug("on_alloc widget=%s, allocation=%s" % (widget, allocation))

        self._allocation = allocation

        w = min(self.allocation.width-2, 70*mkit.EM)
        widget.set_size_request(w, -1)
        return True

    def _header_on_allocate(self, widget, allocation, spacing):
        LOG_ALLOCATION.debug("on_alloc widget=%s, allocation=%s" % (widget, allocation))
        w = allocation.width - self.icon.allocation.width - 2*spacing
        if self.review_stats_widget.get_property('visible'):
            w -= self.review_stats_widget.allocation.width

        self.title.set_size_request(w, -1)
        return

    def _on_realize(self, widget):
        self.addons_statusbar.hide_all()
        return

    def _on_homepage_clicked(self, button):
        import webbrowser
        webbrowser.open_new_tab(self.app_details.website)
        return

    def _layout_page(self):
        # setup widgets
        alignment = gtk.Alignment(0.5, 0.0, yscale=1.0)
        self.add(alignment)

        self.hbox = gtk.HBox()
        alignment.add(self.hbox)

        vb = gtk.VBox(spacing=18)
        vb.set_border_width(20)
        vb.set_redraw_on_allocate(False)
        self.set_redraw_on_allocate(False)
        self.hbox.pack_start(vb, False)

        # header
        hb = gtk.HBox(spacing=12)
        vb.pack_start(hb, False)

        # the app icon
        self.icon = gtk.Image()
        self.icon.set_size_request(84,84)
        self.icon.set_from_icon_name(MISSING_APP_ICON, gtk.ICON_SIZE_DIALOG)
        hb.pack_start(self.icon, False)

        # the app title/summary
        self.title = mkit.EtchedLabel('<span font_desc="bold 20">Title</span>\nSummary')
        self.title.set_alignment(0, 0.5)
        self.title.set_line_wrap(True)
#        self.title.set_ellipsize(pango.ELLIPSIZE_END)
        vb_inner=gtk.VBox(spacing=6)
        vb_inner.pack_start(self.title)

        # usage
        self.usage = mkit.BubbleLabel()
        vb_inner.pack_start(self.usage)

        # star rating widget
        a = gtk.Alignment(0.0, 0.5)
        self.review_stats_widget.star_rating.set_paint_style(StarPainter.STYLE_BIG)
        a.add(self.review_stats_widget)
        hb.pack_end(a, False)

        vb_inner.set_property("can-focus", True)
        self.title.a11y = vb_inner.get_accessible()
        self.title.a11y.set_role(atk.ROLE_PANEL)
        hb.pack_start(vb_inner)

        # the package status bar
        self.pkg_statusbar = PackageStatusBar(self)
        vb.pack_start(self.pkg_statusbar, False)

        # installed where widget
        self.installed_where_hbox = gtk.HBox(spacing=6)
        self.installed_where_hbox.a11y = self.installed_where_hbox.get_accessible()
        vb.pack_start(self.installed_where_hbox, False)

        # the hbox that hold the description on the left and the screenshot 
        # thumbnail on the right
        body_hb = gtk.HBox(spacing=12)
        vb.pack_start(body_hb, False)

        # append the description widget, hold the formatted long description
        self.desc = AppDescription(viewport=self)
        self.desc.description.set_property("can-focus", True)
        self.desc.description.a11y = self.desc.description.get_accessible()
        body_hb.pack_start(self.desc)

        # the thumbnail/screenshot
        self.screenshot = ScreenshotThumbnail(get_distro(), self.icons)
        right_vb = gtk.VBox(spacing=6)
        body_hb.pack_start(right_vb, False)
        right_vb.pack_start(self.screenshot, False)

        # the weblive test-drive stuff
        self.weblive = get_weblive_backend()
        self.test_drive = gtk.Button(_("Test drive"))
        self.test_drive.connect("clicked", self.on_test_drive_clicked)
        right_vb.pack_start(self.test_drive, expand=False, fill=False)

        # attach to all the WebLive events
        self.weblive.client.connect("progress", self.on_weblive_progress)
        self.weblive.client.connect("connected", self.on_weblive_connected)
        self.weblive.client.connect("disconnected", self.on_weblive_disconnected)
        self.weblive.client.connect("exception", self.on_weblive_exception)
        self.weblive.client.connect("warning", self.on_weblive_warning)

        # homepage link button
        self.homepage_btn = mkit.HLinkButton(_('Website'))
        self.homepage_btn.connect('clicked', self._on_homepage_clicked)
        self.homepage_btn.set_underline(True)
        self.homepage_btn.set_xmargin(0)

        # add the links footer to the description widget
        footer_hb = gtk.HBox(spacing=6)
        footer_hb.pack_start(self.homepage_btn, False)
        self.desc.pack_start(footer_hb, False)

        self.info_vb = info_vb = gtk.VBox(spacing=12)
        vb.pack_start(info_vb, False)

        # add-on handling
        self.addon_view = self.addons_manager.table
        info_vb.pack_start(self.addon_view, False)

        self.addons_statusbar = self.addons_manager.status_bar
        self.addon_view.pack_start(self.addons_statusbar, False)
        self.addon_view.connect('table-built', self._on_addon_table_built)

        # package info
        self.info_keys = []

        # info header
        self.info_header = mkit.EtchedLabel(_("Details"))
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

        # reviews cascade
        self.reviews.connect("new-review", self._on_review_new)
        self.reviews.connect("report-abuse", self._on_review_report_abuse)
        self.reviews.connect("submit-usefulness", self._on_review_submit_usefulness)
        self.reviews.connect("more-reviews-clicked", self._on_more_reviews_clicked)
        self.reviews.connect("different-review-language-clicked", self._on_reviews_in_different_language_clicked)
        vb.pack_start(self.reviews, False)

        self.show_all()

        # signals!
        hb.connect('size-allocate', self._header_on_allocate, hb.get_spacing())
        vb.connect('expose-event', self._on_expose, alignment)
        vb.connect('size-allocate', self._on_allocate)

        vb.connect('key-press-event', self._on_key_press)
        return

    def _on_key_press(self, widget, event):
        kv = event.keyval

        # key values we want to respond to
        uppers = (gtk.keysyms.KP_Up, gtk.keysyms.Up)
        downers = (gtk.keysyms.KP_Down, gtk.keysyms.Down)

        if kv in uppers or kv in downers:
            # get the ScrolledWindow adjustments and tweak them appropriately
            if not self.parent: return False

            # the ScrolledWindow vertical-adjustment
            v_adj = self.parent.get_vadjustment()

            # scroll up
            if kv in uppers:
                v = max(v_adj.value - v_adj.step_increment,
                        v_adj.lower)

            # scroll down 
            elif kv in downers:
                v = min(v_adj.value + v_adj.step_increment,
                        v_adj.upper - v_adj.page_size)

            # set our new value
            v_adj.set_value(v)

            # do not share the event with other widgets
            return True
        # share the event with other widgets
        return False

    def _on_review_new(self, button):
        self._review_write_new()

    def _on_review_report_abuse(self, button, review_id):
        self._review_report_abuse(str(review_id))

    def _on_review_submit_usefulness(self, button, review_id, is_useful):
        self._review_submit_usefulness(review_id, is_useful)

    def _update_title_markup(self, appname, summary):
        # make title font size fixed as they should look good compared to the 
        # icon (also fixed).
        markup = '<span font_desc="bold 20">%s</span>\n<span font_desc="9">%s</span>'
        markup = markup % (appname, gobject.markup_escape_text(summary))

        self.title.set_markup(markup)
        self.title.a11y.set_name(appname + '. ' + summary)
        return

    def _update_app_icon(self, app_details):

        pb = self._get_icon_as_pixbuf(app_details)
        # should we show the green tick?
#        self._show_overlay = app_details.pkg_state == PKG_STATE_INSTALLED
        w, h = pb.get_width(), pb.get_height()

        tw = self.APP_ICON_SIZE - 10 # bit of a fudge factor
        if pb.get_width() < tw:
            pb = pb.scale_simple(tw, tw, gtk.gdk.INTERP_TILES)

        self.icon.set_from_pixbuf(pb)
        return

    def _update_layout_error_status(self, pkg_error):
        # if we have an error or if we need to enable a source
        # then hide everything else
        if pkg_error:
            self.addon_view.hide()
            self.reviews.hide()
            self.screenshot.hide()
            self.info_header.hide()
            self.info_vb.hide()
        else:
            self.addon_view.show()
            self.reviews.show()
            self.screenshot.show()
            self.info_header.show()
            self.info_vb.show()
        return

    def _update_app_description(self, app_details, appname):
        # format new app description
        if app_details.pkg_state == PKG_STATE_ERROR:
            description = app_details.error
        else:
            description = app_details.description
        if not description:
            description = " "
        self.desc.set_description(description, appname)

        # a11y for description
        self.desc.description.a11y.set_name(description)
        return

    def _update_description_footer_links(self, app_details):        
        # show or hide the homepage button and set uri if homepage specified
        if app_details.website:
            self.homepage_btn.show()
            self.homepage_btn.set_tooltip_text(app_details.website)
        else:
            self.homepage_btn.hide()
        return

    def _update_app_screenshot(self, app_details):
        # get screenshot urls and configure the ScreenshotView...
        if app_details.thumbnail and app_details.screenshot:
            self.screenshot.configure(app_details)

            # inititate the download and display series of callbacks
            self.screenshot.download_and_display()
        return

    def _update_weblive(self, app_details):
        self.desktop_file = app_details.desktop_file
        # only enable test drive if we have a desktop file and exec line
        if (not self.weblive.ready or
            not self.weblive.is_pkgname_available_on_server(app_details.pkgname) or
            not os.path.exists(self.desktop_file) or
            not get_exec_line_from_desktop(self.desktop_file)):
            self.test_drive.hide()
        else:
            self.test_drive.show()
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
        if self.addon_view.parent:
            self.info_vb.remove(self.addon_view)

        if not app_details.error:
            self.addons_manager.configure(app_details.pkgname)

        # Update total size label
        self.totalsize_info.set_value(_("Calculating..."))
        gobject.timeout_add(500, self.update_totalsize)

        # Update addons state bar
        self.addons_statusbar.configure()
        return

    def _update_all(self, app_details):
        # reset view to top left
        self.get_vadjustment().set_value(0)
        self.get_hadjustment().set_value(0)

        # set button sensitive again
        self.pkg_statusbar.button.set_sensitive(True)

        pkg_ambiguous_error = app_details.pkg_state in (PKG_STATE_NOT_FOUND,
                                                        PKG_STATE_NEEDS_SOURCE)

        appname = gobject.markup_escape_text(app_details.display_name)

        if app_details.pkg_state == PKG_STATE_NOT_FOUND:
            summary = app_details._error_not_found
        else:
            summary = app_details.display_summary
        if not summary:
            summary = ""

        # hide stuff
        self.usage.hide()

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

        self._update_layout_error_status(pkg_ambiguous_error)
        self._update_title_markup(appname, summary)
        self._update_app_icon(app_details)
        self._update_app_description(app_details, appname)
        self._update_description_footer_links(app_details)
        self._update_app_screenshot(app_details)
        self._update_weblive(app_details)
        self._update_pkg_info_table(app_details)
        self._update_addons(app_details)
        self._update_reviews(app_details)

        # show where it is
        self._configure_where_is_it()

        # async query zeitgeist and rnr
        self._update_usage_counter()
        return

    def _update_minimal(self, app_details):
        self._update_app_icon(app_details)
        self._update_pkg_info_table(app_details)
#        self._update_addons_minimal(app_details)

        # depending on pkg install state set action labels
        self.pkg_statusbar.configure(app_details, app_details.pkg_state)

#        # show where it is
        self._configure_where_is_it()
        return

    def _add_where_is_it_commandline(self, pkgname):
        cmdfinder = CmdFinder(self.cache)
        cmds = cmdfinder.find_cmds_from_pkgname(pkgname)
        if not cmds: 
            return
        vb = gtk.VBox(spacing=3)
        self.installed_where_hbox.pack_start(vb, False)
        msg = gettext.ngettext(
            _('This program is run from a terminal: '),
            _('These programs are run from a terminal: '),
            len(cmds))
        title = gtk.Label()
        title.set_alignment(0, 0)
        title.set_markup(msg)
        title.set_line_wrap(True)
        title.set_size_request(self.allocation.width-24, -1)
        vb.pack_start(title, False, padding=3)
        cmds_str = ", ".join(cmds)
        cmd_label = gtk.Label(
            '<span font_desc="monospace bold 9">%s</span>' % cmds_str)
        cmd_label.set_selectable(True)
        cmd_label.set_use_markup(True)
        cmd_label.set_alignment(0, 0.5)
        cmd_label.set_padding(12, 0)
        cmd_label.set_line_wrap(True)
        cmd_label.set_size_request(self.allocation.width-64, -1)
        vb.pack_start(cmd_label, False)
        self.installed_where_hbox.show_all()

    def _add_where_is_it_launcher(self, where):
        # disable where-is-it under Unity as it does not apply there
        if is_unity_running():
            return
        # display launcher location
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

    def _configure_where_is_it(self):
        # remove old content
        self.installed_where_hbox.foreach(lambda c: c.destroy())
        self.installed_where_hbox.set_property("can-focus", False)
        self.installed_where_hbox.a11y.set_name('')
        # see if we have the location if its installed
        if self.app_details.pkg_state == PKG_STATE_INSTALLED:
            # first try the desktop file from the DB, then see if
            # there is a local desktop file with the same name as 
            # the package
            desktop_file = None
            searcher = GMenuSearcher()
            pkgname = self.app_details.pkgname
            for p in [self.app_details.desktop_file,
                      "/usr/share/applications/%s.desktop" % pkgname]:
                if p and os.path.exists(p):
                    desktop_file = p
            # try to show menu location if there is a desktop file,
            # but never show commandline programs for apps with desktop 
            # file to cover cases like "file-roller" that have NoDisplay=true
            if desktop_file:
                where = searcher.get_main_menu_path(desktop_file)
                if where:
                    self._add_where_is_it_launcher(where)
            # if there is no desktop file, show commandline
            else:
                self._add_where_is_it_commandline(pkgname)
        return

    # public API
    # FIXME:  port to AppDetailsViewBase as
    #         AppDetailsViewBase.show_app(self, app)
    def show_app(self, app, force=False):
        LOG.debug("AppDetailsView.show_app '%s'" % app)
        if app is None:
            LOG.debug("no app selected")
            return

        same_app = (self.app and 
                    self.app.pkgname and 
                    self.app.appname == app.appname and
                    self.app.pkgname == app.pkgname)
        #print 'SameApp:', same_app

        # init data
        self.app = app
        self.app_details = app.get_details(self.db)
        
        # check if app just became available and if so, force full
        # refresh
        if (same_app and
            self.pkg_state == PKG_STATE_NEEDS_SOURCE and
            self.app_details.pkg_state != PKG_STATE_NEEDS_SOURCE):
            force = True
        self.pkg_state = self.app_details.pkg_state

        # for compat with the base class
        self.appdetails = self.app_details

        # update content
        # layout page
        if same_app and not force:
            self._update_minimal(self.app_details)
        else:
            self._update_all(self.app_details)

        self.title.grab_focus()

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
            # reset the reviews UI now that we have installed the package
            self.reviews.configure_reviews_ui()
        # normal states
        elif state == PKG_STATE_REMOVING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_UNINSTALLED)
        elif state == PKG_STATE_INSTALLING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
        elif state == PKG_STATE_UPGRADING:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
        # addons modified, order is important here
        elif self.addons_statusbar.applying:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
            self.addons_manager.configure(self.app_details.name, False)
            self.addons_statusbar.configure()
        # cancellation of dependency dialog
        elif state == PKG_STATE_INSTALLED:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_INSTALLED)
            # reset the reviews UI now that we have installed the package
            self.reviews.configure_reviews_ui()
        elif state == PKG_STATE_UNINSTALLED:
            self.pkg_statusbar.configure(self.app_details, PKG_STATE_UNINSTALLED)
        self.adjustment_value = None
        
        if self.addons_statusbar.applying:
            self.addons_statusbar.applying = False

        return False

    def _on_transaction_started(self, backend, pkgname, appname, trans_id, trans_type):
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

    def get_app_icon_details(self):
        """ helper for unity dbus support to provide details about the application
            icon as it is displayed on-screen
        """
        icon_size = self._get_app_icon_size_on_screen()
        (icon_x, icon_y) = self._get_app_icon_xy_position_on_screen()
        return (icon_size, icon_x, icon_y)

    def _get_app_icon_size_on_screen(self):
        """ helper for unity dbus support to get the size of the maximum side
            for the application icon as it is displayed on-screen
        """
        icon_size = self.APP_ICON_SIZE
        if self.icon.get_storage_type() == gtk.IMAGE_PIXBUF:
            pb = self.icon.get_pixbuf()
            if pb.get_width() > pb.get_height():
                icon_size = pb.get_width()
            else:
                icon_size = pb.get_height()
        return icon_size
                
    def _get_app_icon_xy_position_on_screen(self):
        """ helper for unity dbus support to get the x,y position of
            the application icon as it is displayed on-screen
        """
        # find toplevel parent
        parent = self
        while parent.get_parent():
            parent = parent.get_parent()
        # get x, y relative to toplevel
        (x,y) = self.icon.translate_coordinates(parent, 0, 0)
        # get toplevel window position
        (px, py) = parent.get_position()
        return (px+x, py+y)
        
    def _get_icon_as_pixbuf(self, app_details):
        if app_details.icon:
            if self.icons.has_icon(app_details.icon):
                try:
                    return self.icons.load_icon(app_details.icon, 84, 0)
                except glib.GError, e:
                    logging.warn("failed to load '%s': %s" % (app_details.icon, e))
                    return self.icons.load_icon(MISSING_APP_ICON, 84, 0)
            elif app_details.icon_needs_download and app_details.icon_url:
                LOG.debug("did not find the icon locally, must download it")

                def on_image_download_complete(downloader, image_file_path):
                    # when the download is complete, replace the icon in the view with the downloaded one
                    try:
                        pb = gtk.gdk.pixbuf_new_from_file(image_file_path)
                        self.icon.set_from_pixbuf(pb)
                    except Exception, e:
                        LOG.warning("couldn't load downloadable icon file '%s': %s" % (image_file_path, e))
                    
                image_downloader = SimpleFileDownloader()
                image_downloader.connect(
                    'file-download-complete', on_image_download_complete)
                image_downloader.download_file(
                    app_details.icon_url, app_details.cached_icon_file_path)
        return self.icons.load_icon(MISSING_APP_ICON, 84, 0)
    
    def update_totalsize(self):
        def pkg_downloaded(pkg_version):
            filename = os.path.basename(pkg_version.filename)
            # FIXME: use relative path here
            return os.path.exists("/var/cache/apt/archives/" + filename)

        if not self.totalsize_info.get_property('visible'):
            return False

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
            if counter <= 100:
                label_string = gettext.ngettext("Used: one time",
                                                "Used: %(amount)s times",
                                                counter) % { 'amount' : counter, }
            else:
                label_string = _("Used: over 100 times")
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
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    # gui
    win = gtk.Window()
    scroll = gtk.ScrolledWindow()
    view = AppDetailsViewGtk(db, distro, icons, cache, datadir, win)
    #view.show_app(Application("Pay App Example", "pay-app"))
    #view.show_app(Application("3D Chess", "3dchess"))
    #view.show_app(Application("Movie Player", "totem"))
    #view.show_app(Application("ACE", "unace"))
    view.show_app(Application("", "apt"))

    #view.show_app("AMOR")
    #view.show_app("Configuration Editor")
    #view.show_app("Artha")
    #view.show_app("cournol")
    #view.show_app("Qlix")

    scroll.add(view)
    scroll.show()
    win.add(scroll)
    win.set_size_request(600,400)
    win.show()
    win.connect('destroy', gtk.main_quit)

    # keep it spinning to test for re-draw issues and memleaks
    #glib.timeout_add_seconds(2, _show_app, view)


    # run it
    gtk.main()
