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
import glib
import gobject
import gtk
import logging
import pango
import os
import time
import xapian

import aptdaemon.client
from gettext import gettext as _

from softwarecenter.backend.channel import ChannelsManager
from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *

from widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage

LOG = logging.getLogger(__name__)

class ViewSwitcher(gtk.TreeView):

    __gsignals__ = {
        "view-changed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT),
                         ),
    }


    def __init__(self, view_manager, datadir, db, cache, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.view_manager = view_manager
        self.datadir = datadir
        self.icons = icons
        if not store:
            store = ViewSwitcherList(view_manager, datadir, db, cache, icons)
            # FIXME: this is just set here for app.py, make the
            #        transactions-changed signal part of the view api
            #        instead of the model
            self.model = store
            self.set_model(store)
        gtk.TreeView.__init__(self)
        
        tp = CellRendererAnimatedImage()
        column = gtk.TreeViewColumn("Icon")
        column.pack_start(tp, expand=False)
        column.set_attributes(tp, image=store.COL_ICON)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column.pack_start(tr, expand=True)
        column.set_attributes(tr, markup=store.COL_NAME)
        self.append_column(column)

        # Remember the previously selected permanent view
        self._permanent_views = PERMANENT_VIEWS
        self._previous_permanent_view = None

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))
        
        self.set_model(store)
        self.set_headers_visible(False)
        self.get_selection().set_select_function(self.on_treeview_selected)
        self.set_level_indentation(4)
        self.set_enable_search(False)

        self.selected_channel_name = None
        self.selected_channel_installed_only = False
        
        self.connect("row-expanded", self.on_treeview_row_expanded)
        self.connect("row-collapsed", self.on_treeview_row_collapsed)
        self.connect("cursor-changed", self.on_cursor_changed)
        self.connect("event", self.on_event)

        self.get_model().connect("channels-refreshed", self._on_channels_refreshed)
        self.get_model().connect("row-deleted", self._on_row_deleted)
        
    def on_treeview_row_expanded(self, widget, iter, path):
        # do nothing on a node expansion
        pass
        
    def on_treeview_row_collapsed(self, widget, iter, path):
        # on a node collapse, select the node
        self.set_cursor(path)
    
    def on_treeview_selected(self, path):
        model = self.get_model()
        iter_ = model.get_iter(path)
        id_ = model.get_value(iter_, 2)
        if id_ == VIEW_PAGE_SEPARATOR_1:
            return False
        return True
        
    def on_cursor_changed(self, widget):
        (path, column) = self.get_cursor()
        model = self.get_model()
        action = model[path][ViewSwitcherList.COL_ACTION]
        channel = model[path][ViewSwitcherList.COL_CHANNEL]
        if action in self._permanent_views:
            self._previous_permanent_view = path
        self.selected_channel_name = model[path][ViewSwitcherList.COL_NAME]
        if channel:
            self.selected_channel_installed_only = channel.installed_only

        view_page = action
        self.emit("view-changed", view_page, channel)
        
    def on_event(self, widget, event):
        # Deal with keypresses on the viewswitcher
        if event.type == gtk.gdk.KEY_PRESS:
            # Get the toplevel node of the currently selected row
            toplevel = self.get_toplevel_node(self.get_cursor())
            toplevel_path = (toplevel,)

            # Expand the toplevel node if the right arrow key is clicked
            if event.keyval == KEYPRESS_RIGHT_ARROW:
                if not self.row_expanded(toplevel_path):
                    self.expand_row(toplevel_path, False)
            # Collapse the toplevel node if the left arrow key is clicked
            if event.keyval == KEYPRESS_LEFT_ARROW:
                if self.row_expanded(toplevel_path):
                    self.collapse_row(toplevel_path)
        
    def get_view(self):
        """return the current activated view number or None if no
           view is activated (this can happen when a pending view 
           disappeared). Views are:
           
           VIEW_PAGE_AVAILABLE
           VIEW_PAGE_CHANNEL
           VIEW_PAGE_INSTALLED
           VIEW_PAGE_HISTORY
           VIEW_PAGE_PENDING
        """
        (path, column) = self.get_cursor()
        if not path:
            return None
        return path[0]
    
    def get_toplevel_node(self, cursor):
        """Returns the toplevel node of a selected row"""
        (path, column) = cursor
        return path[0]

    def set_view(self, view_page):
        notebook_page_id = self.view_manager.get_notebook_page_from_view_id(view_page)
        self.set_cursor((notebook_page_id,))
        self.emit("view-changed", view_page, None)

    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
            
    def expand_row(self, path, open_all):
        model = self.get_model()
        if model:
            super(ViewSwitcher, self).expand_row(path, open_all)
            
    def collapse_row(self, path):
        model = self.get_model()
        if model:
            super(ViewSwitcher, self).collapse_row(path)
            
    def expand_available_node(self):
        """ expand the available pane node in the viewswitcher pane """
        self.expand_row(model.get_path(model.available_iter), False)
            
    def is_available_node_expanded(self):
        """ return True if the available pane node in the viewswitcher pane is expanded """
        model = self.get_model()
        expanded = False
        if model:
            expanded = self.row_expanded(model.get_path(model.available_iter))
        return expanded
        
    def expand_installed_node(self):
        """ expand the installed pane node in the viewswitcher pane """
        self.expand_row(model.get_path(model.installed_iter), False)
            
    def is_installed_node_expanded(self):
        """ return True if the installed pane node in the viewswitcher pane is expanded """
        model = self.get_model()
        expanded = False
        if model:
            expanded = self.row_expanded(model.get_path(model.installed_iter))
        return expanded
        
    def select_channel_node(self, channel_name, installed_only):
        """ select the specified channel node """
        model = self.get_model()
        if model:
            channel_iter_to_select = model.get_channel_iter_for_name(channel_name,
                                                                     installed_only)
            if channel_iter_to_select:
                self.set_cursor(model.get_path(channel_iter_to_select))

    def _on_channels_refreshed(self, model):
        """
        when channels are refreshed, the viewswitcher channel is unselected so
        we need to reselect it
        """
        model = self.get_model()
        if model:
            channel_iter_to_select = model.get_channel_iter_for_name(
                self.selected_channel_name,
                self.selected_channel_installed_only)
            if channel_iter_to_select:
                self.set_cursor(model.get_path(channel_iter_to_select))

    def _on_row_deleted(self, widget, path):
        (path, column) = self.get_cursor()
        if path is None:
            # The view that was selected has been deleted, switch back to
            # the previously selected permanent view.
            if self._previous_permanent_view is not None:
                self.set_cursor(self._previous_permanent_view)

class ViewSwitcherList(gtk.TreeStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION,
     COL_CHANNEL,
     ) = range(4)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    __gsignals__ = {'channels-refreshed':(gobject.SIGNAL_RUN_FIRST,
                                          gobject.TYPE_NONE,
                                          ())}


    def __init__(self, view_manager, datadir, db, cache, icons):
        gtk.TreeStore.__init__(self, 
                               AnimatedImage, 
                               str, 
                               gobject.TYPE_PYOBJECT, 
                               gobject.TYPE_PYOBJECT,
                               ) # must match columns above
        self.view_manager = view_manager
        self.icons = icons
        self.datadir = datadir
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed", self.on_transactions_changed)
        self.backend.connect("transaction-finished", self.on_transaction_finished)
        self.backend.connect("channels-changed", self.on_channels_changed)
        self.db = db
        self.cache = cache
        self.distro = get_distro()
        # pending transactions
        self._pending = 0
        # setup the normal stuff

        # first, the availablepane items
        available_icon = self._get_icon("softwarecenter")
        self.available_iter = self.append(None, [available_icon, _("Get Software"), VIEW_PAGE_AVAILABLE, None])

        # the installedpane items
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        self.installed_iter = self.append(None, [icon, _("Installed Software"), VIEW_PAGE_INSTALLED, None])
        
        # the channelpane 
        self.channel_manager = ChannelsManager(db, icons)
        # do initial channel list update
        self._update_channel_list()
        
        # the historypane item
        icon = self._get_icon("clock")
        history_iter = self.append(None, [icon, _("History"), VIEW_PAGE_HISTORY, None])
        icon = AnimatedImage(None)
        self.append(None, [icon, "<span size='1'> </span>", VIEW_PAGE_SEPARATOR_1, None])
        
        # the progress pane is build on demand

    def on_channels_changed(self, backend, res):
        LOG.debug("on_channels_changed %s" % res)
        if res:
            self.db.open()
            self._update_channel_list()

    def on_transactions_changed(self, backend, total_transactions):
        LOG.debug("on_transactions_changed '%s'" % total_transactions)
        pending = len(total_transactions)
        if pending > 0:
            for row in self:
                if row[self.COL_ACTION] == VIEW_PAGE_PENDING:
                    row[self.COL_NAME] = _("In Progress (%i)") % pending
                    break
            else:
                icon = AnimatedImage(self.ANIMATION_PATH)
                icon.start()
                self.append(None, [icon, _("In Progress (%i)") % pending, 
                             VIEW_PAGE_PENDING, None])
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

    def _update_channel_list(self):
        self._update_channel_list_available_view()
        self._update_channel_list_installed_view()
        self.emit("channels-refreshed")
        
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
                        channel.get_channel_icon(),
                        channel.get_channel_display_name(),
                        VIEW_PAGE_CHANNEL,
                        channel])
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
            query = channel.get_channel_query()
            enquire.set_query(query)
            matches = enquire.get_mset(0, len(self.db))
            # only check channels that have a small number of items
            add_channel_item = True
            if len(matches) < 200:
                add_channel_item = False
                for m in matches:
                    doc = m[xapian.MSET_DOCUMENT]
                    pkgname = self.db.get_pkgname(doc)
                    if (pkgname in self.cache and
                        self.cache[pkgname].is_installed):
                        add_channel_item = True
                        break
            if add_channel_item:
                self.append(self.installed_iter, [
                            channel.get_channel_icon(),
                            channel.get_channel_display_name(),
                            VIEW_PAGE_CHANNEL,
                            channel])
        # delete the old ones
        for child in iters_to_kill:
            self.remove(child)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    scroll = gtk.ScrolledWindow()
    icons = gtk.icon_theme_get_default()

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache(apt.progress.text.OpProgress())
    db = StoreDatabase(pathname, cache)
    db.open()

    view = ViewSwitcher(datadir, db, icons)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
