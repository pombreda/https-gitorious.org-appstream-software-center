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

from softwarecenter.backend.channel import SoftwareChannel
from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.db.database import StoreDatabase
from softwarecenter.enums import *

from widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage

class ViewSwitcher(gtk.TreeView):

    __gsignals__ = {
        "view-changed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (int, gobject.TYPE_PYOBJECT),
                         ),
    }


    def __init__(self, datadir, db, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.datadir = datadir
        self.icons = icons
        if not store:
            store = ViewSwitcherList(datadir, db, icons)
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

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))
        
        self.set_model(store)
        self.set_headers_visible(False)
        self.get_selection().set_select_function(self.on_treeview_selected)
        self.set_level_indentation(4)
        self.set_enable_search(False)
        
        self.connect("row-expanded", self.on_treeview_row_expanded)
        self.connect("row-collapsed", self.on_treeview_row_collapsed)
        self.connect("cursor-changed", self.on_cursor_changed)
        
    def on_treeview_row_expanded(self, widget, iter, path):
        # do nothing on a node expansion
        pass
        
    def on_treeview_row_collapsed(self, widget, iter, path):
        # on a node collapse, select the node
        self.set_cursor(path)
    
    def on_treeview_selected(self, path):
        if path[0] == ViewSwitcherList.ACTION_ITEM_SEPARATOR_1:
            return False
        return True
        
    def on_cursor_changed(self, widget):
        (path, column) = self.get_cursor()
        model = self.get_model()
        action = model[path][ViewSwitcherList.COL_ACTION]
        channel = model[path][ViewSwitcherList.COL_CHANNEL]
        self.emit("view-changed", action, channel)
        
    def get_view(self):
        """return the current activated view number or None if no
           view is activated (this can happen when a pending view 
           disappeared). Views are:
           
           ViewSwitcherList.ACTION_ITEM_AVAILABLE
           ViewSwitcherList.ACTION_ITEM_CHANNEL
           ViewSwitcherList.ACTION_ITEM_INSTALLED
           ViewSwitcherList.ACTION_ITEM_PENDING
        """
        (path, column) = self.get_cursor()
        if not path:
            return None
        return path[0]
    def set_view(self, action):
        self.set_cursor((action,))
        self.emit("view-changed", action, None)
    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)

class ViewSwitcherList(gtk.TreeStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION,
     COL_CHANNEL) = range(4)

    # items in the treeview
    (ACTION_ITEM_AVAILABLE,
     ACTION_ITEM_INSTALLED,
     ACTION_ITEM_SEPARATOR_1,
     ACTION_ITEM_PENDING,
     ACTION_ITEM_CHANNEL) = range(5)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    def __init__(self, datadir, db, icons):
        gtk.TreeStore.__init__(self, AnimatedImage, str, int, gobject.TYPE_PYOBJECT)
        self.icons = icons
        self.datadir = datadir
        self.backend = get_install_backend()
        self.backend.connect("transactions-changed", self.on_transactions_changed)
        self.db = db
        self.distro = get_distro()
        # pending transactions
        self._pending = 0
        # setup the normal stuff
        available_icon = self._get_icon("softwarecenter")
        available_iter = self.append(None, [available_icon, _("Get Software"), self.ACTION_ITEM_AVAILABLE, None])
        
        # get list of software channels
        from softwarecenter.utils import ExecutionTime
        with ExecutionTime("TIME self._get_channels()"):
            channels = self._get_channels()
        
        # check current set of channel origins in the apt cache to see if anything
        # has changed, and refresh the channel list if needed
        with ExecutionTime("TIME self._get_origins_from_cache()"):
            cache_origins = self._get_origins_from_cache()
        
        for origin in cache_origins:
            print "cache origin is: %s" % origin
            
        db_origins = set()
        for channel in channels:
            if channel.get_channel_origin():
                db_origins.add(channel.get_channel_origin())
                
        for origin in db_origins:
            print "db origin is: %s" % origin
            
        if cache_origins != db_origins:
            print "origins in cache do not match origins in xapian, must do an update-apt-xapian-database"
        
        # iterate the channels and add as subnodes of the available node
        for channel in channels:
            print channel
            self.append(available_iter, [channel.get_channel_icon(),
                                         channel.get_channel_display_name(),
                                         self.ACTION_ITEM_CHANNEL,
                                         channel])
        
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        installed_iter = self.append(None, [icon, _("Installed Software"), self.ACTION_ITEM_INSTALLED, None])
        icon = AnimatedImage(None)
        self.append(None, [icon, "<span size='1'> </span>", self.ACTION_ITEM_SEPARATOR_1, None])

    def on_transactions_changed(self, backend, total_transactions):
        logging.debug("on_transactions_changed '%s'" % total_transactions)
        print "on_transactions_changed '%s'" % total_transactions
        pending = len(total_transactions)
        if pending > 0:
            for row in self:
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    row[self.COL_NAME] = _("In Progress (%i)") % pending
                    break
            else:
                icon = AnimatedImage(self.ANIMATION_PATH)
                icon.start()
                self.append(None, [icon, _("In Progress (%i)") % pending, 
                             self.ACTION_ITEM_PENDING, None])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    del self[(i,)]
            print "UPDATE channels here?"
                    
    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon
        
    def _get_origins_from_cache(self):
        """
        return a set of the current channel origins from the apt.Cache
        """
        origins = set()
        for pkg in apt.Cache():
            for item in pkg.candidate.origins:
                if item.origin:
                    origins.add(item.origin)
        return origins
        
    def _get_channels(self):
        """
        return a list of SoftwareChannel objects in display order
        ordered according to:
            Distribution, Partners, PPAs alphabetically, Other channels alphabetically,
            Unknown channel last
        """
        distro_channel_name = self.distro.get_distro_channel_name()
        
        # gather the set of software channels and order them
        other_channel_list = []
        for channel_iter in self.db.xapiandb.allterms("XOL"):
            if len(channel_iter.term) == 3:
                continue
            channel_name = channel_iter.term[3:]
            
            # get origin information for this channel
            m = self.db.xapiandb.postlist_begin(channel_iter.term)
            doc = self.db.xapiandb.get_document(m.get_docid())
            for term_iter in doc.termlist():
                if term_iter.term.startswith("XOO") and len(term_iter.term) > 3: 
                    channel_origin = term_iter.term[3:]
                    break
            logging.debug("channel_name: %s" % channel_name)
            logging.debug("channel_origin: %s" % channel_origin)
            other_channel_list.append((channel_name, channel_origin))
        
        dist_channel = []
        ppa_channels = []
        other_channels = []
        unknown_channel = []
        
        for (channel_name, channel_origin) in other_channel_list:
            if not channel_name:
                unknown_channel.append(SoftwareChannel(self.icons, 
                                                       channel_name,
                                                       channel_origin,
                                                       None))
            elif channel_name == distro_channel_name:
                dist_channel = (SoftwareChannel(self.icons,
                                                distro_channel_name,
                                                channel_origin,
                                                None,
                                                filter_required=True))
            elif channel_origin and channel_origin.startswith("LP-PPA"):
                ppa_channels.append(SoftwareChannel(self.icons, 
                                                    channel_name,
                                                    channel_origin,
                                                    None))
            # TODO: detect generic repository source (e.g., Google, Inc.)
            else:
                other_channels.append(SoftwareChannel(self.icons, 
                                                      channel_name,
                                                      channel_origin,
                                                      None))
        # FIXME: do not hardcode this, check instead for 
        #        self.db.xapiandb.allterms("AH") and add all of those
        #        and provide a mechanism in the channel to check
        #        both origin (XAO) and channel name from app-install (AH)
        # FIXME2: pass the AH name as well so that we do not need to special
        #         case the AH query for partner
        # also get the partner repository
        partner_channel = SoftwareChannel(self.icons, 
                                          distro_channel_name,
                                          None,
                                          "partner")
        
        # set them in order
        channels = []
        channels.append(dist_channel)
        channels.append(partner_channel)
        channels.extend(ppa_channels)
        channels.extend(other_channels)
        channels.extend(unknown_channel)
        
        return channels

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
    cache = apt.Cache(apt.progress.OpTextProgress())
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
