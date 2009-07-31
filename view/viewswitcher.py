#!/usr/bin/python

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
    def __init__(self, store):
        gtk.TreeView.__init__(self)
        self.set_fixed_height_mode(True)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=store.COL_ICON)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=store.COL_NAME)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        self.set_model(store)
        #self.set_headers_visible(False)
        #self.set_grid_lines(False)
        #self.set_enable_tree_lines(False)
        #self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)


class ViewList(gtk.ListStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION) = range(3)

    # items in the treeview
    (ITEM_AVAILABLE,
     ITEM_INSTALLED,
     ITEM_PENDING) = range(3)

    def __init__(self):
        gtk.ListStore.__init__(self, gtk.gdk.Pixbuf, str, int)
        # setup the normal stuff
        self.append([None, _("Get new software"), self.ITEM_AVAILABLE])
        self.append([None, _("Installed software"), self.ITEM_INSTALLED])
        # setup dbus
        self.system_bus = dbus.SystemBus()
        obj = self.system_bus.get_object("org.debian.apt",
                                         "/org/debian/apt")
        self.aptd = dbus.Interface(obj, 'org.debian.apt')
        # check for pending aptdaemon actions
        gobject.timeout_add_seconds(1, self.check_pending)

    def check_pending(self):
        print "check_pending"
        (foo, transactions) = self.aptd.GetActiveTransactions()
        if len(transactions) > 0:
            self.append([None, _("Pending (%i)") % len(transactions),
                         self.ITEM_PENDING])
        else:
            # remove
            for itm in self:
                if itm[self.COL_ACTION] == self.ITEM_PENDING:
                    self.remove(itm)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # now the store
    store = ViewList()

    # gui
    scroll = gtk.ScrolledWindow()
    view = ViewSwitcher(store)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
