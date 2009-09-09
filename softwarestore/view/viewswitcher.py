# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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
import gtk
import gobject
import logging
import os
import time
import xapian
import pango

import aptdaemon.client

from gettext import gettext as _

from animatedimage import CellRendererAnimatedImage, AnimatedImage

class ViewSwitcher(gtk.TreeView):
    def __init__(self, datadir, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.datadir = datadir
        self.icons = icons
        if not store:
            store = ViewSwitcherList(datadir, icons)
            self.set_model(store)
        gtk.TreeView.__init__(self)
        tp = CellRendererAnimatedImage()
        column = gtk.TreeViewColumn("Icon", tp, image=store.COL_ICON)
        #column.set_fixed_width(32)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn("Name", tr, markup=store.COL_NAME)
        #column.set_fixed_width(200)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        self.set_model(store)
        self.set_headers_visible(False)
        self.connect("button-press-event", self.on_button_press_event)
    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
    def on_button_press_event(self, widget, event):
        #print "on_button_press_event: ", event
        res = self.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        if event.button != 1 or path is None:
            return
        self.emit("row-activated", path, column)

class ViewSwitcherList(gtk.ListStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION) = range(3)

    # items in the treeview
    (ACTION_ITEM_NONE,
     ACTION_ITEM_AVAILABLE,
     ACTION_ITEM_INSTALLED,
     ACTION_ITEM_PENDING) = range(4)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/32x32/status/software-store-progress-*.png"

    def __init__(self, datadir, icons):
        gtk.ListStore.__init__(self, AnimatedImage, str, int)
        self.icons = icons
        self.datadir = datadir
        # setup the normal stuff
        icon = AnimatedImage(self.icons.load_icon("software-store", self.ICON_SIZE, 0))
        self.append([icon, _("Get Free Software"), self.ACTION_ITEM_AVAILABLE])
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        self.append([icon, _("Installed Software"), self.ACTION_ITEM_INSTALLED])
        #not working
        #icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 24, 2)
        #icon.fill(0)
        #self.append([AnimatedImage(icon), '', self.ACTION_ITEM_NONE])

        # watch the daemon exit and (re)register the signal
        bus = dbus.SystemBus()
        self._owner_watcher = bus.watch_name_owner(
            "org.debian.apt", self._register_active_transactions_watch)

    def _register_active_transactions_watch(self, connection):
        #print "_register_active_transactions_watch", connection
        self.aptd = aptdaemon.client.get_aptdaemon()
        self.aptd.connect_to_signal("ActiveTransactionsChanged", self.check_pending)
        current, queued = self.aptd.GetActiveTransactions()
        self.check_pending(current, queued)

    def check_pending(self, current, queue):
        #print "check_pending"
        pending = 0
        if current or len(queue) > 0:
            pending = 1 + len(queue)
        # if we have a pending item, show it in the action view
        # and if not, delete any items we added already
        if pending > 0:
            for row in self:
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    row[self.COL_NAME] = _("In Progress (%i)") % pending
                    break
            else:
                icon = AnimatedImage(self.ANIMATION_PATH)
                icon.start()
                pendingrow = self.append([icon, _("Pending (%i)") % pending, 
                             self.ACTION_ITEM_PENDING])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    del self[(i,)]
        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-store"

    scroll = gtk.ScrolledWindow()
    icons = gtk.icon_theme_get_default()
    view = ViewSwitcher(datadir, icons)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
