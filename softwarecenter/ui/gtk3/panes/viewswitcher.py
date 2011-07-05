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
from gi.repository import GObject
from gi.repository import Gtk, Gdk
import logging
import os

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import ViewPages
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.distro import get_distro

from softwarecenter.ui.gtk3.panes.views.widgets.buttons import CategoryTile
from softwarecenter.ui.gtk3.em import StockEms


LOG = logging.getLogger(__name__)


class ViewSwitcherLogic(GObject.GObject):

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    __gsignals__ = {'channels-refreshed':(GObject.SignalFlags.RUN_FIRST,
                                          None,
                                          ())}

    def __init__(self, view_manager, datadir, db, cache, icons):
        GObject.GObject.__init__(self)

        self.view_manager = view_manager
        self.icons = icons
        self.datadir = datadir
        self.db = db
        self.cache = cache
        self.distro = get_distro()

        # pending transactions
        self._pending = 0
        
        # Remember the previously selected permanent view
        self._permanent_views = ViewPages.PERMANENT_VIEWS
        self._previous_permanent_view = None

        # emit a transactions-changed signal to ensure that we display any
        # pending transactions
        self.backend = get_install_backend()
        self.backend.emit("transactions-changed", self.backend.pending_transactions)

    def on_transactions_changed(self, backend, total_transactions):
        LOG.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        if pending > 0:
            # do pending animation stuff here
            pass

    def on_transaction_finished(self, backend, result):
        if result.success:
            self._update_channel_list_installed_view()
            self.emit("channels-refreshed")

    #~ @wait_for_apt_cache_ready
    def _update_channel_list(self):
        self._update_channel_list_available_view()
        self._update_channel_list_installed_view()
        self.emit("channels-refreshed")

    def _update_channel_list_available_view(self):
        # check what needs to be cleared. we need to append first, kill
        # afterward because otherwise a row without children is collapsed
        # by the view.
        pass

    def _update_channel_list_installed_view(self):
        # see comments for _update_channel_list_available_view() method above
        child = self.iter_children(self.installed_iter)
        iters_to_kill = set()
        while child:
            iters_to_kill.add(child)
            child = self.iter_next(child)
        # iterate the channels and add as subnodes of the installed node
        for channel in self.channel_manager.channels_installed_only:
            # check for no installed items for each channel and do not
            # append the channel item in this case
            enquire = xapian.Enquire(self.db.xapiandb)
            query = channel.query
            enquire.set_query(query)
            matches = enquire.get_mset(0, len(self.db))
            # only check channels that have a small number of items
            add_channel_item = True
            if len(matches) < 200:
                add_channel_item = False
                for m in matches:
                    doc = m.document
                    pkgname = self.db.get_pkgname(doc)
                    if (pkgname in self.cache and
                        self.cache[pkgname].is_installed):
                        add_channel_item = True
                        break
            if add_channel_item:
                # append channels here
                pass


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

        # first, the availablepane items
        self.view_buttons.append(self._make_button(
                                    _("All Software"),
                                    "softwarecenter"))

        #~ self.available_button.set_image(available_icon)

        # the installedpane items
        self.view_buttons.append(self._make_button(
                                    _("Installed"),
                                    "computer"))

        # the channelpane 
        #~ self.channel_manager = ChannelsManager(db, icons)
        # do initial channel list update
        #~ self._update_channel_list()

        # the historypane item
        self.view_buttons.append(self._make_button(
                                    _("History"),
                                    "document-open-recent"))

        view_ids = (ViewPages.AVAILABLE, ViewPages.INSTALLED,
                    ViewPages.HISTORY)

        for view_id, btn in zip(view_ids, self.view_buttons):
            self.pack_start(btn, False, False, 0)
            btn.connect('clicked', self.do_view_switch, view_id)
            btn.show()

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))

    def _make_button(self, label, icon_name):
        t = CategoryTile(label, icon_name, self.ICON_SIZE)
        t.set_size_request(-1, -1)
        return t

    def do_view_switch(self, button, view_id):
        self.view_manager.set_active_view(view_id)
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
