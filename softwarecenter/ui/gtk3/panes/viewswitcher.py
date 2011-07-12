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
from softwarecenter.distro import get_distro

from softwarecenter.backend.channel import ChannelsManager
from softwarecenter.ui.gtk3.widgets.buttons import SectionSelector
from softwarecenter.ui.gtk3.em import StockEms
import softwarecenter.ui.gtk3.dialogs as dialogs

LOG = logging.getLogger(__name__)


class ViewSwitcherLogic(object):

    #~ ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    def __init__(self, view_manager, datadir, db, cache, icons):
        self.view_manager = view_manager
        self.channel_manager = ChannelsManager(db)
        self.backend = get_install_backend()

    def get_available_channels(self):
        return self.channel_manager.channels

    def get_installed_channels(self):
        # todo, filter out channels for which not packages are installed
        return self.channel_manager.channels

    #~ def on_transactions_changed(self, backend, total_transactions):
        #~ LOG.debug("on_transactions_changed '%s'" % total_transactions)
        #~ pending = len(total_transactions)
        #~ if pending > 0:
            #~ # do pending animation stuff here
            #~ pass
#~ 
    #~ def on_transaction_finished(self, backend, result):
        #~ if result.success:
            #~ self._update_channel_list_installed_view()
#~ 
    #~ @wait_for_apt_cache_ready
    #~ def _update_channel_list(self):
        #~ self._update_channel_list_available_view()
        #~ self._update_channel_list_installed_view()
#~ 
    #~ def _update_channel_list_available_view(self):
        #~ pass
#~ 
    #~ def _update_channel_list_installed_view(self):
        #~ pass


class ViewSwitcher(Gtk.HBox, ViewSwitcherLogic):

    __gsignals__ = {
        "view-changed" : (GObject.SignalFlags.RUN_LAST,
                          None, 
                          (GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT),
                         ),
    }


    ICON_SIZE = Gtk.IconSize.BUTTON

    def __init__(self, view_manager, datadir, db, cache, icons):
        Gtk.ButtonBox.__init__(self)
        self.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.set_spacing(StockEms.XLARGE)

        ViewSwitcherLogic.__init__(self, view_manager, datadir, db, cache, icons)

        # Gui stuff
        self.view_buttons = []
        self._handlers = []

        # first, the availablepane items
        available = self._make_button(_("All Software"),
                                      "softwarecenter")
        available.set_channel_request_func(
                                    self.on_get_available_channels)
        self.view_buttons.append(available)

        # the installedpane items
        installed = self._make_button(_("Installed"),
                                      "computer")
        installed.set_channel_request_func(
                                    self.on_get_installed_channels)
        self.view_buttons.append(installed)

        # the historypane item
        self.view_buttons.append(self._make_button(
                                    _("History"),
                                    "document-open-recent",
                                    display_dropdown=False))

        # the pendingpane
        self.view_buttons.append(self._make_button(
                                    _("Progress"),
                                    "gtk-execute",
                                    display_dropdown=False))

        # order is important here, should match button order/length
        view_ids = (ViewPages.AVAILABLE, ViewPages.INSTALLED,
                    ViewPages.HISTORY, ViewPages.PENDING)

        for view_id, btn in zip(view_ids, self.view_buttons):
            self.pack_start(btn, False, False, 0)
            btn.connect('clicked', self.on_view_switch, view_id)
            btn.show()

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))

    def _make_button(self, label, icon_name, display_dropdown=True):
        return SectionSelector(label, icon_name, self.ICON_SIZE,
                               has_channel_sel=display_dropdown)

    def on_view_switch(self, button, view_id):
        #~ pane = self.view_manager.get_view_widget(view_id)
        #~ pane.state.reset()
        self.view_manager.set_active_view(view_id)
        return

    def on_get_available_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.AVAILABLE)

    def on_get_installed_channels(self, popup):
        return self.build_channel_list(popup, ViewPages.INSTALLED)

    def build_channel_list(self, popup, view_id):
        # clean up old signal handlers
        for sig in self._handlers:
            GObject.source_remove(sig)

        channels = self.get_available_channels()
        for i, channel in enumerate(channels):
            item = Gtk.ImageMenuItem.new_with_label(channel.display_name)
            image = Gtk.Image.new_from_icon_name(channel.icon, Gtk.IconSize.BUTTON)
            item.set_image(image)
            item.set_always_show_image(True)
            self._handlers.append(
                item.connect(
                    "activate",
                    self.on_channel_selected,
                    channel,
                    view_id
                )
            )
            popup.attach(item, 0, 1, i, i+1)

        popup.show_all()
        return

    def on_channel_selected(self, item, channel, view_id):
        # set active pane
        vm = self.view_manager
        pane = vm.set_active_view(view_id)

        # configure DisplayState
        pane.state.channel = channel

        # request page change
        vm.display_page(pane, pane.Pages.LIST, pane.state)
        return


if __name__ == "__main__":
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    # xapian
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    try:
        db = StoreDatabase(pathname, cache)
        db.open()
    except xapian.DatabaseOpeningError:
        # Couldn't use that folder as a database
        # This may be because we are in a bzr checkout and that
        #   folder is empty. If the folder is empty, and we can find the
        # script that does population, populate a database in it.
        if os.path.isdir(pathname) and not os.listdir(pathname):
            from softwarecenter.db.update import rebuild_database
            logging.info("building local database")
            rebuild_database(pathname)
            db = StoreDatabase(pathname, cache)
            db.open()
    except xapian.DatabaseCorruptError, e:
        logging.exception("xapian open failed")
        dialogs.error(None, 
                      _("Sorry, can not open the software database"),
                      _("Please re-install the 'software-center' "
                        "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)


    logging.basicConfig(level=logging.DEBUG)
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    from softwarecenter.ui.gtk3.utils import get_sc_icon_theme
    icons = get_sc_icon_theme(datadir)

    scroll = Gtk.ScrolledWindow()

    from softwarecenter.ui.gtk3.session.viewmanager import ViewManager
    notebook = Gtk.Notebook()
    manager = ViewManager(notebook)
    view = ViewSwitcher(manager, datadir, db, cache, icons)

    box = Gtk.VBox()
    box.pack_start(scroll, True, True, 0)

    win = Gtk.Window()
    scroll.add_with_viewport(view)

    win.add(box)
    win.set_size_request(400,400)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)

    Gtk.main()
