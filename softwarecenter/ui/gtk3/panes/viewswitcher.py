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


from gi.repository import Gtk, GObject
import logging
import os
import sys
import xapian

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import ViewPages
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.backend.channel import get_channels_manager
from softwarecenter.ui.gtk3.widgets.buttons import SectionSelector
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.symbolic_icons import (
                                    SymbolicIcon, PendingSymbolicIcon)
import softwarecenter.ui.gtk3.dialogs as dialogs


LOG = logging.getLogger(__name__)


class ViewSwitcher(Gtk.Box):

    __gsignals__ = {
        "view-changed" : (GObject.SignalFlags.RUN_LAST,
                          None, 
                          (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT),
                         ),
    }


    ICON_SIZE = Gtk.IconSize.LARGE_TOOLBAR

    def __init__(self, view_manager, datadir, db, cache, icons):
        # boring stuff
        self.view_manager = view_manager
        self.channel_manager = get_channels_manager(db)

        # backend sig handlers ...
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed",
                             self.on_transaction_changed)
        self.backend.connect("transaction-finished",
                             self.on_transaction_finished)
        self.backend.connect("channels-changed",
                             self.on_channels_changed)

        # widgetry
        Gtk.Box.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(StockEms.SMALL)

        # Gui stuff
        self.view_buttons = {}
        self._handlers = []
        self._prev_item = None

        # order is important here!
        # first, the availablepane items
        icon = SymbolicIcon("available")
        available = self.append_section(ViewPages.AVAILABLE,
                                        _("All Software"),
                                        icon,
                                        True)
        available.set_build_func(self.on_get_available_channels)

        # the installedpane items
        icon = SymbolicIcon("installed")
        installed = self.append_section(ViewPages.INSTALLED,
                                        _("Installed"),
                                        icon,
                                        True)
        installed.set_build_func(self.on_get_installed_channels)

        # the historypane item
        icon = SymbolicIcon("history")
        self.append_section(ViewPages.HISTORY, _("History"), icon)

        # the pendingpane
        icon = PendingSymbolicIcon("pending")
        self.append_section(ViewPages.PENDING, _("Progress"), icon)

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))

    def on_transaction_changed(self, backend, total_transactions):
        LOG.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        self.notify_icon_of_pending_count(pending)
        if pending > 0:
            self.start_icon_animation()
        else:
            self.stop_icon_animation()
        return

    def start_icon_animation(self):
        # the pending button ProgressImage is special, see:
        # softwarecenter/ui/gtk3/widgets/animatedimage.py
        self.view_buttons[ViewPages.PENDING].image.start()

    def stop_icon_animation(self):
        # the pending button ProgressImage is special, see:
        # softwarecenter/ui/gtk3/widgets/animatedimage.py
        self.view_buttons[ViewPages.PENDING].image.stop()

    def notify_icon_of_pending_count(self, count):
        image = self.view_buttons[ViewPages.PENDING].image
        image.set_transaction_count(count)

    def on_transaction_finished(self, backend, result):
        if result.success: self.on_channels_changed()
        return

    def on_section_sel_toggled(self, button, view_id):
        prev_active = self.get_active_section_selector()
        if prev_active is not None:
            prev_active.set_active(False)
        self.view_manager.set_active_view(view_id)
        return

    def on_get_available_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.AVAILABLE)

    def on_get_installed_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.INSTALLED)

    def on_channels_changed(self):
        for view_id, btn in self.view_buttons.iteritems():
            if not btn.has_channel_sel: continue
            # setting popup to None will cause a rebuild of the popup
            # menu the next time the selector is clicked
            btn.popup = None
        return

    def append_section(self, view_id, label, icon, has_channel_sel=False):
        btn = SectionSelector(label, icon, self.ICON_SIZE,
                              has_channel_sel)
        self.view_buttons[view_id] = btn
        self.pack_start(btn, False, False, 0)
        btn.show()
        btn.connect("toggled", self.on_section_sel_toggled, view_id)
        return btn

    def build_channel_list(self, popup, view_id):
        # clean up old signal handlers
        for sig in self._handlers:
            GObject.source_remove(sig)

        if view_id == ViewPages.AVAILABLE:
            channels = self.channel_manager.get_available_channels()
        elif view_id == ViewPages.INSTALLED:
            channels = self.channel_manager.get_installed_channels()
        else:
            channels = self.channel_manager.channels

        for i, channel in enumerate(channels):
            item = Gtk.CheckMenuItem()
            item.set_draw_as_radio(True)

            label = Gtk.Label.new(channel.display_name)
            image = Gtk.Image.new_from_icon_name(channel.icon, Gtk.IconSize.MENU)

            box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, StockEms.MEDIUM)
            box.pack_start(image, False, False, 0)
            box.pack_start(label, False, False, 0)

            item.add(box)
            item.show_all()

            self._handlers.append(
                item.connect(
                    "button-release-event",
                    self.on_channel_selected,
                    channel,
                    view_id
                )
            )
            popup.attach(item, 0, 1, i, i+1)

        if self.view_manager.is_active_view(view_id):
            first = popup.get_children()[0]
            first.set_property("active", True)
            self._prev_item = first
        return

    def get_active_section_selector(self):
        for view_id, btn in self.view_buttons.iteritems():
            if btn.get_active():
                return btn
        return None

    def on_channel_selected(self, item, event, channel, view_id):

        if self._prev_item is item:
            parent = item.get_parent()
            parent.hide()
            return True

        if self._prev_item is not None:
            self._prev_item.set_property("active", False)

        self._prev_item = item

        # set active pane
        vm = self.view_manager
        pane = vm.set_active_view(view_id)

        # configure DisplayState
        state = pane.state.copy()
        state.channel = channel

        # request page change
        if channel.origin == "all":
            page = pane.Pages.HOME
        else:
            page = pane.Pages.LIST

        GObject.idle_add(vm.display_page, pane, page, state)
        return


def get_test_window_viewswitcher():
    from softwarecenter.db.pkginfo import get_pkg_info
    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    from softwarecenter.ui.gtk3.session.viewmanager import ViewManager
    import softwarecenter.paths

    cache = get_pkg_info()
    cache.open()

    db = StoreDatabase(softwarecenter.paths.XAPIAN_BASE_PATH+"/xapian", cache)
    db.open()

    icons = get_sc_icon_theme(softwarecenter.paths.datadir)
    scroll = Gtk.ScrolledWindow()

    notebook = Gtk.Notebook()
    manager = ViewManager(notebook)
    view = ViewSwitcher(manager, softwarecenter.paths.datadir, db, cache, icons)

    box = Gtk.VBox()
    box.pack_start(scroll, True, True, 0)

    win = Gtk.Window()
    scroll.add_with_viewport(view)

    win.add(box)
    win.set_size_request(400,200)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    return win

if __name__ == "__main__":
    import sys    
    import softwarecenter.paths
    logging.basicConfig(level=logging.DEBUG)

    softwarecenter.paths.datadir = "./data"
    win = get_test_window_viewswitcher()


    Gtk.main()
