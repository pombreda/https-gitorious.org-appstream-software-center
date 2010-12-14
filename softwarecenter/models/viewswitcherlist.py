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


import gobject
import gtk
import logging
import xapian

from gettext import gettext as _

from softwarecenter.backend.channel import ChannelsManager
from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.enums import *
from softwarecenter.utils import wait_for_apt_cache_ready

from softwarecenter.view.widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage

LOG = logging.getLogger(__name__)

class ViewSwitcherList(gtk.TreeStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION,
     COL_CHANNEL,
     COL_BUBBLE_TEXT,
     ) = range(5)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    __gsignals__ = {'channels-refreshed':(gobject.SIGNAL_RUN_FIRST,
                                          gobject.TYPE_NONE,
                                          ())}


    def __init__(self, view_manager, datadir, db, cache, icons):
        gtk.TreeStore.__init__(self,
                               AnimatedImage,         # COL_ICON
                               str,                   # COL_NAME
                               gobject.TYPE_PYOBJECT, # COL_ACTION
                               gobject.TYPE_PYOBJECT, # COL_CHANNEL
                               str,                   # COL_BUBBLE_TEXT
                               ) # must match columns above
        self.view_manager = view_manager
        self.icons = icons
        self.datadir = datadir
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed", self.on_transactions_changed)
        self.backend.connect("transaction-finished", self.on_transaction_finished)
        self.db = db
        self.cache = cache
        self.distro = get_distro()
        # pending transactions
        self._pending = 0
        # setup the normal stuff

        # first, the availablepane items
        available_icon = self._get_icon("softwarecenter")
        self.available_iter = self.append(None, [available_icon, _("Get Software"), VIEW_PAGE_AVAILABLE, None, None])

        # the installedpane items
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        self.installed_iter = self.append(None, [icon, _("Installed Software"), VIEW_PAGE_INSTALLED, None, None])
        
        # the channelpane 
        self.channel_manager = ChannelsManager(db, icons)
        # do initial channel list update
        self._update_channel_list()

        # the historypane item
        icon = self._get_icon("clock")
        history_iter = self.append(None, [icon, _("History"), VIEW_PAGE_HISTORY, None, None])
        icon = AnimatedImage(None)
        self.append(None, [icon, "<span size='1'> </span>", VIEW_PAGE_SEPARATOR_1, None, None])
        
        # the progress pane is build on demand

        # emit a transactions-changed signal to ensure that we display any
        # pending transactions
        self.backend.emit("transactions-changed", self.backend.pending_transactions)

    def on_transactions_changed(self, backend, total_transactions):
        LOG.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        if pending > 0:
            for row in self:
                if row[self.COL_ACTION] == VIEW_PAGE_PENDING:
                    row[self.COL_BUBBLE_TEXT] = str(pending)
                    break
            else:
                icon = AnimatedImage(self.ANIMATION_PATH)
                icon.start()
                self.append(None, [icon, "In Progress...", 
                             VIEW_PAGE_PENDING, None, str(pending)])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == VIEW_PAGE_PENDING:
                    del self[(i,)]
                    
    def on_transaction_finished(self, backend, result):
        if result.success:
            self._update_channel_list_installed_view()
            self.emit("channels-refreshed")

    def get_channel_iter_for_name(self, channel_name, installed_only):
        """ get the liststore iterator for the given name, consider
            installed-only too because channel names may be duplicated
        """ 
        LOG.debug("get_channel_iter_for_name %s %s" % (channel_name,
                                                       installed_only))
        def _get_iter_for_channel_name(it):
            """ internal helper """
            while it:
                if self.get_value(it, self.COL_NAME) == channel_name:
                    return it
                it = self.iter_next(it)
            return None

        # check root iter first
        channel_iter_for_name = _get_iter_for_channel_name(self.get_iter_root())
        if channel_iter_for_name:
            LOG.debug("found '%s' on root level" % channel_name)
            return channel_iter_for_name

        # check children
        if installed_only:
            parent_iter = self.installed_iter
        else:
            parent_iter = self.available_iter
        LOG.debug("looking at path '%s'" % self.get_path(parent_iter))
        child = self.iter_children(parent_iter)
        channel_iter_for_name = _get_iter_for_channel_name(child)
        return channel_iter_for_name
                    
    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon

    @wait_for_apt_cache_ready
    def _update_channel_list(self):
        self._update_channel_list_available_view()
        self._update_channel_list_installed_view()
        self.emit("channels-refreshed")
        
    # FIXME: this way of updating is really not ideal because it
    #        will trigger set_cursor signals and that causes the
    #        UI to behave funny if the user is in a channel view
    #        and the backend sends a channels-changed signal
    def _update_channel_list_available_view(self):
        # check what needs to be cleared. we need to append first, kill
        # afterward because otherwise a row without children is collapsed
        # by the view.
        # 
        # normally GtkTreeIters have a limited life-cycle and are no
        # longer valid after the model changed, fortunately with the
        # gtk.TreeStore (that we use) they are persisent
        child = self.iter_children(self.available_iter)
        iters_to_kill = set()
        while child:
            iters_to_kill.add(child)
            child = self.iter_next(child)
        # iterate the channels and add as subnodes of the available node
        for channel in self.channel_manager.channels:
            self.append(self.available_iter, [
                        channel.icon,
                        channel.display_name,
                        VIEW_PAGE_CHANNEL,
                        channel,
                        None])
        # delete the old ones
        for child in iters_to_kill:
            self.remove(child)
    
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
                self.append(self.installed_iter, [
                            channel.icon,
                            channel.display_name,
                            VIEW_PAGE_CHANNEL,
                            channel,
                            None])
        # delete the old ones
        for child in iters_to_kill:
            self.remove(child)

