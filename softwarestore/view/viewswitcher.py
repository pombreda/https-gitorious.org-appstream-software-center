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

import logging
import gtk
import gobject
import apt
import os
import xapian
import time
import dbus

from gettext import gettext as _

class ViewSwitcher(gtk.TreeView):
    def __init__(self, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.icons = icons
        if not store:
            store = ViewSwitcherList(icons)
            self.set_model(store)
        gtk.TreeView.__init__(self)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=store.COL_ICON)
        #column.set_fixed_width(32)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=store.COL_NAME)
        #column.set_fixed_width(200)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        self.set_model(store)
        self.set_headers_visible(False)
        self.connect("button-press-event", self.on_button_press_event)
    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(event.x, event.y)
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
    def on_button_press_event(self, widget, event):
        #print "on_button_press_event: ", event
        res = self.get_path_at_pos(event.x, event.y)
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

    ICON_SIZE = 32

    def __init__(self, icons):
        gtk.ListStore.__init__(self, gtk.gdk.Pixbuf, str, int)
        self.icons = icons
        # setup the normal stuff
        icon = self.icons.load_icon("software-store", self.ICON_SIZE, 0)
        self.append([icon, _("Get Free software"), self.ACTION_ITEM_AVAILABLE])
        icon = self.icons.load_icon("gtk-harddisk", self.ICON_SIZE, 0)
        self.append([icon, _("Installed software"), self.ACTION_ITEM_INSTALLED])
        # spacer - not working
        #icon = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8,
        #                     self.ICON_SIZE/4.0, self.ICON_SIZE/4.0)
        #icon.fill(0)
        #self.append([icon, '<span size="xx-small"></span>', 
        #             self.ACTION_ITEM_NONE])

        # setup dbus, its ok if aptdaemon is not available, we just
	# do not show the pending changes tab then

        # FIXME: use ActiveTransactionChanged callback from the daemon
        #        here instead of polling
        try:
            self.system_bus = dbus.SystemBus()
            obj = self.system_bus.get_object("org.debian.apt",
                                             "/org/debian/apt")
            self.aptd = dbus.Interface(obj, 'org.debian.apt')
            # check for pending aptdaemon actions
            self.check_pending()
            gobject.timeout_add_seconds(1, self.check_pending)
        except dbus.exceptions.DBusException, e:
            logging.exception("aptdaemon dbus error")

    def check_pending(self):
        #print "check_pending"
        pending = 0
        (current, queue) = self.aptd.GetActiveTransactions()
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
                self.append([None, _("Pending (%i)") % pending, 
                             self.ACTION_ITEM_PENDING])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    del self[(i,)]
        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    scroll = gtk.ScrolledWindow()
    icons = gtk.icon_theme_get_default()
    view = ViewSwitcher(icons)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
