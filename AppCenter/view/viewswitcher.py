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
    def __init__(self, store=None):
        if not store:
            store = ViewSwitcherList()
            self.set_model(store)
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
        self.set_headers_visible(False)
        #self.set_headers_visible(False)
        #self.set_grid_lines(False)
        #self.set_enable_tree_lines(False)
        #self.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_NONE)

class ViewSwitcherList(gtk.ListStore):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION) = range(3)

    # items in the treeview
    (ACTION_ITEM_AVAILABLE,
     ACTION_ITEM_INSTALLED,
     ACTION_ITEM_PENDING) = range(3)

    def __init__(self):
        gtk.ListStore.__init__(self, gtk.gdk.Pixbuf, str, int)
        # setup the normal stuff
        self.append([None, _("Get new software"), self.ACTION_ITEM_AVAILABLE])
        self.append([None, _("Installed software"), self.ACTION_ITEM_INSTALLED])
        # setup dbus, its ok if aptdaemon is not available, we just
	# do not show the pending changes tab then
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
