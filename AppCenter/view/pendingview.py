#!/usr/bin/python

import logging
import gtk
import gobject
import apt
import os
import xapian
import time

import aptdaemon.client
from aptdaemon.enums import *

class PendingStore(gtk.ListStore):

    # column names
    (COL_TID,
     COL_ICON, 
     COL_NAME, 
     COL_STATUS, 
     COL_PROGRESS) = range(5)

    def __init__(self, icons):
        # icon, status, progress
        gtk.ListStore.__init__(self, str, gtk.gdk.Pixbuf, str, str, float)
        # the apt-daemon stuff
        self.apt_client = aptdaemon.client.AptClient()
        self.apt_daemon = aptdaemon.client.get_aptdaemon()
        self.apt_daemon.connect_to_signal("ActiveTransactionsChanged",
                                          self.on_transactions_changed)
        self._signals = []
        self.icons = icons

    def clear(self):
        super(PendingStore, self).clear()
        for sig in self._signals:
            gobject.source_remove(sig)
        self._signals = []

    def on_transactions_changed(self, current_tid, pending_tids):
        #print "on_transaction_changed", current_tid, len(pending_tids)
        self.clear()
        for tid in [current_tid]+pending_tids:
            if not tid:
                continue
            trans = aptdaemon.client.get_transaction(tid)
            self._signals.append(
                trans.connect("progress", self._on_progress_changed))
            self._signals.append(
                trans.connect("status", self._on_status_changed))
            #FIXME: role is always "Applying changes"
            #self._signals.append(
            #    trans.connect("role", self._on_role_changed))
            appname = trans.get_data("appname")
            iconname = trans.get_data("iconname")
            if iconname:
                icon = self.icons.load_icon(iconname, 24, 0)
            else:
                icon = None
            self.append([tid, icon, appname, "", 0.0])
            del trans

    def _on_role_changed(self, trans, role):
        #print "_on_progress_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_NAME] = get_role_localised_present_from_enum(role)

    def _on_progress_changed(self, trans, progress):
        #print "_on_progress_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_PROGRESS] = progress

    def _on_status_changed(self, trans, status):
        #print "_on_progress_changed: ", trans, status
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_STATUS] = get_status_string_from_enum(status)


class PendingView(gtk.TreeView):
    def __init__(self, icons):
        gtk.TreeView.__init__(self)
        self.set_headers_visible(False)
        # icon
        self.icons = icons
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=PendingStore.COL_ICON)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        # name
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=PendingStore.COL_NAME)
        #column.set_fixed_width(200)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        # progress
        tp = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn("Progress", tp, 
                                    value=PendingStore.COL_PROGRESS,
                                    text=PendingStore.COL_STATUS)
        self.append_column(column)
        # add it
        store = PendingStore(icons)
        self.set_model(store)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    icons = gtk.icon_theme_get_default()
    view = PendingView(icons)

    # gui
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    win = gtk.Window()
    win.add(scroll)
    view.grab_focus()
    win.set_size_request(500,200)
    win.show_all()

    gtk.main()
