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
import sys

import aptdaemon.client
from aptdaemon.enums import *

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

class PendingStore(gtk.ListStore):

    # column names
    (COL_TID,
     COL_ICON, 
     COL_NAME, 
     COL_STATUS, 
     COL_PROGRESS,
     COL_CANCEL) = range(6)

    # icons
    PENDING_STORE_ICON_CANCEL = gtk.STOCK_CANCEL
    PENDING_STORE_ICON_NO_CANCEL = "" # gtk.STOCK_YES


    def __init__(self, icons):
        # icon, status, progress
        gtk.ListStore.__init__(self, str, gtk.gdk.Pixbuf, str, str, float, str)
        # data
        self.icons = icons
        # the apt-daemon stuff
        self.apt_client = aptdaemon.client.AptClient()
        self.apt_daemon = aptdaemon.client.get_aptdaemon()
        self.apt_daemon.connect_to_signal("ActiveTransactionsChanged",
                                          self.on_transactions_changed)
        # FIXME: reconnect if the daemon exists
        self._signals = []
        # do a initial check
        current, queued = self.apt_daemon.GetActiveTransactions()
        self.on_transactions_changed(current, queued)


    def clear(self):
        super(PendingStore, self).clear()
        for sig in self._signals:
            gobject.source_remove(sig)
            del sig
        self._signals = []

    def on_transactions_changed(self, current_tid, pending_tids):
        ICON_SIZE = 32
        
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
            self._signals.append(
                trans.connect("allow-cancel", self._on_allow_cancel_changed))
            #FIXME: role is always "Applying changes"
            #self._signals.append(
            #    trans.connect("role", self._on_role_changed))
            appname = trans.get_data("appname")
            iconname = trans.get_data("iconname")
            if iconname:
                try:
                    icon = self.icons.load_icon(iconname, ICON_SIZE, 0)
                except Exception, e:
                    icon = self.icons.load_icon(MISSING_APP_ICON, ICON_SIZE, 0)
            else:
                icon = self.icons.load_icon(MISSING_APP_ICON, ICON_SIZE, 0)
            self.append([tid, icon, appname, "", 0.0, ""])
            del trans

    def _on_allow_cancel_changed(self, trans, allow_cancel):
        #print "_on_allow_cancel: ", trans, allow_cancel
        for row in self:
            if row[self.COL_TID] == trans.tid:
                if allow_cancel:
                    row[self.COL_CANCEL] = self.PENDING_STORE_ICON_CANCEL
                else:
                    row[self.COL_CANCEL] = self.PENDING_STORE_ICON_NO_CANCEL

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
                # FIXME: the spaces around %s are poor mans padding because
                #        setting xpad on the cell-renderer seems to not work
                row[self.COL_STATUS] = "  %s  " % get_status_string_from_enum(status)


class PendingView(gtk.TreeView):
    
    CANCEL_XPAD = 4

    def __init__(self, icons):
        gtk.TreeView.__init__(self)
        # customization
        self.set_headers_visible(False)
        self.connect("button-press-event", self._on_button_pressed)
        # icon
        self.icons = icons
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=PendingStore.COL_ICON)
        #column.set_fixed_width(32)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        # name
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=PendingStore.COL_NAME)
        self.append_column(column)
        # progress
        tp = gtk.CellRendererProgress()
        column = gtk.TreeViewColumn("Progress", tp, 
                                    value=PendingStore.COL_PROGRESS,
                                    text=PendingStore.COL_STATUS)
        self.append_column(column)
        # cancel icon
        tp = gtk.CellRendererPixbuf()
        tp.set_property("xpad", self.CANCEL_XPAD)
        column = gtk.TreeViewColumn("Cancel", tp, 
                                    stock_id=PendingStore.COL_CANCEL)
        self.append_column(column)
        # fake columns that eats the extra space at the end
        tt = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Cancel", tt)
        self.append_column(column)
        # add it
        store = PendingStore(icons)
        self.set_model(store)
    def _on_button_pressed(self, widget, event):
        """button press handler to capture clicks on the cancel button"""
        #print "_on_clicked: ", event
        if event == None or event.button != 1:
            return
        res = self.get_path_at_pos(event.x, event.y)
        if not res:
            return
        (path, column, wx, wy) = res
        # no path
        if not path:
            return
        # wrong column
        if column.get_title() != "Cancel":
            return
        # not cancelable (no icon)
        model = self.get_model()
        if model[path][PendingStore.COL_CANCEL] == "":
            return 
        # get tid
        tid = model[path][PendingStore.COL_TID]
        trans = aptdaemon.client.get_transaction(tid)
        trans.cancel()

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
