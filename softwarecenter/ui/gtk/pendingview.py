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

import dbus
import glib
import gtk
import gobject
import logging

from softwarecenter.utils import get_icon_from_theme, size_to_str
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.transactionswatcher import get_transactions_watcher
from basepane import BasePane

from gettext import gettext as _

class PendingStore(gtk.ListStore):

    # column names
    (COL_TID,
     COL_ICON, 
     COL_NAME, 
     COL_STATUS, 
     COL_PROGRESS,
     COL_PULSE,
     COL_CANCEL) = range(7)

    # column types
    column_types = (str,             # COL_TID
                    gtk.gdk.Pixbuf,  # COL_ICON
                    str,             # COL_NAME
                    str,             # COL_STATUS
                    float,           # COL_PROGRESS
                    int,            # COL_PULSE
                    str)             # COL_CANCEL

    # icons
    PENDING_STORE_ICON_CANCEL = gtk.STOCK_CANCEL
    PENDING_STORE_ICON_NO_CANCEL = "" # gtk.STOCK_YES

    ICON_SIZE = 24

    def __init__(self, icons):
        # icon, status, progress
        gtk.ListStore.__init__(self, *self.column_types)
        self._transactions_watcher = get_transactions_watcher()
        self._transactions_watcher.connect("lowlevel-transactions-changed",
                                           self._on_lowlevel_transactions_changed)
        # data
        self.icons = icons
        # the apt-daemon stuff
        self.backend = get_install_backend()
        self._signals = []
        # let the pulse helper run
        glib.timeout_add(500, self._pulse_purchase_helper)

    def clear(self):
        super(PendingStore, self).clear()
        for sig in self._signals:
            gobject.source_remove(sig)
            del sig
        self._signals = []

    def _on_lowlevel_transactions_changed(self, watcher, current_tid, pending_tids):
        logging.debug("on_transaction_changed %s (%s)" % (current_tid, len(pending_tids)))
        self.clear()
        for tid in [current_tid] + pending_tids:
            if not tid:
                continue
            # we do this synchronous (it used to be a reply_handler)
            # otherwise we run into a race that
            # when we get two on_transaction_changed closely after each
            # other clear() is run before the "_append_transaction" handler
            # is run and we end up with two (or more) _append_transactions
            trans = self._transactions_watcher.get_transaction(tid)
            self._append_transaction(trans)
        # add pending purchases as pseudo transactions
        for pkgname in self.backend.pending_purchases:
            iconname = self.backend.pending_purchases[pkgname].iconname
            icon = get_icon_from_theme(self.icons, iconname=iconname, iconsize=self.ICON_SIZE)
            appname = self.backend.pending_purchases[pkgname].appname
            status_text = self._render_status_text(
                appname or pkgname, _(u'Installing purchase\u2026'))
            self.append([pkgname, icon, pkgname, status_text, 0, 1, None])

    def _pulse_purchase_helper(self):
        for item in self:
            if item[self.COL_PULSE] > 0:
                self[-1][self.COL_PULSE] += 1
        return True

    def _append_transaction(self, trans):
        """Extract information about the transaction and append it to the
        store.
        """
        logging.debug("_append_transaction %s (%s)" % (trans.tid, trans))
        self._signals.append(
            trans.connect(
                "progress-details-changed", self._on_progress_details_changed))
        self._signals.append(
            trans.connect("progress-changed", self._on_progress_changed))
        self._signals.append(
            trans.connect("status-changed", self._on_status_changed))
        self._signals.append(
            trans.connect(
                "cancellable-changed",self._on_cancellable_changed))

        if "sc_appname" in trans.meta_data:
            appname = trans.meta_data["sc_appname"]
        elif "sc_pkgname" in trans.meta_data:
            appname = trans.meta_data["sc_pkgname"]
        else:
            #FIXME: Extract information from packages property
            appname = trans.get_role_description()
            self._signals.append(
                trans.connect("role-changed", self._on_role_changed))
        try:
            iconname = trans.meta_data["sc_iconname"]
        except KeyError:
            icon = get_icon_from_theme(self.icons, iconsize=self.ICON_SIZE)
        else:
            icon = get_icon_from_theme(self.icons, iconname=iconname, iconsize=self.ICON_SIZE)
        if trans.is_waiting():
            status = trans.status_details
        else:
            status = trans.get_status_description()
        status_text = self._render_status_text(appname, status)
        cancel_icon = self._get_cancel_icon(trans.cancellable)
        self.append([trans.tid, icon, appname, status_text, trans.progress,
                     -1, cancel_icon])

    def _on_cancellable_changed(self, trans, cancellable):
        #print "_on_allow_cancel: ", trans, allow_cancel
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_CANCEL] = self._get_cancel_icon(cancellable)

    def _get_cancel_icon(self, cancellable):
        if cancellable:
            return self.PENDING_STORE_ICON_CANCEL
        else:
            return self.PENDING_STORE_ICON_NO_CANCEL

    def _on_role_changed(self, trans, role):
        #print "_on_progress_changed: ", trans, role
        for row in self:
            if row[self.COL_TID] == trans.tid:
                row[self.COL_NAME] = trans.get_role_description(role)

    def _on_progress_details_changed(self, trans, current_items, total_items,
                                     current_bytes, total_bytes, current_cps,
                                     eta):
        #print "_on_progress_details_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                if trans.is_downloading():
                    name = row[self.COL_NAME]
                    current_bytes_str = size_to_str(current_bytes)
                    total_bytes_str = size_to_str(total_bytes)
                    status = _("Downloaded %sB of %sB") % \
                             (current_bytes_str, total_bytes_str)
                    row[self.COL_STATUS] = self._render_status_text(name, status)

    def _on_progress_changed(self, trans, progress):
        # print "_on_progress_changed: ", trans, progress
        for row in self:
            if row[self.COL_TID] == trans.tid:
                if progress:
                    row[self.COL_PROGRESS] = progress

    def _on_status_changed(self, trans, status):
        #print "_on_progress_changed: ", trans, status
        for row in self:
            if row[self.COL_TID] == trans.tid:
                # FIXME: the spaces around %s are poor mans padding because
                #        setting xpad on the cell-renderer seems to not work
                name = row[self.COL_NAME]
                if trans.is_waiting():
                    st = trans.status_details
                else:
                    st = trans.get_status_description(status)
                row[self.COL_STATUS] = self._render_status_text(name, st)

    def _render_status_text(self, name, status):
        if not name:
            name = ""
        return "%s\n<small>%s</small>" % (name, status)


class PendingView(gtk.ScrolledWindow, BasePane):
    
    CANCEL_XPAD = 6
    CANCEL_YPAD = 6

    def __init__(self, icons):
        gtk.ScrolledWindow.__init__(self)
        BasePane.__init__(self)
        self.tv = gtk.TreeView()
        # customization
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.add(self.tv)
        self.tv.set_headers_visible(False)
        self.tv.connect("button-press-event", self._on_button_pressed)
        # icon
        self.icons = icons
        tp = gtk.CellRendererPixbuf()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=PendingStore.COL_ICON)
        self.tv.append_column(column)
        # name
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Name", tr, markup=PendingStore.COL_STATUS)
        column.set_min_width(200)
        column.set_expand(True)
        self.tv.append_column(column)
        # progress
        tp = gtk.CellRendererProgress()
        tp.set_property("xpad", self.CANCEL_XPAD)
        tp.set_property("ypad", self.CANCEL_YPAD)
        tp.set_property("text", "")
        column = gtk.TreeViewColumn("Progress", tp, 
                                    value=PendingStore.COL_PROGRESS,
                                    pulse=PendingStore.COL_PULSE)
        column.set_min_width(200)
        self.tv.append_column(column)
        # cancel icon
        tpix = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Cancel", tpix, 
                                    stock_id=PendingStore.COL_CANCEL)
        self.tv.append_column(column)
        # fake columns that eats the extra space at the end
        tt = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Cancel", tt)
        self.tv.append_column(column)
        # add it
        store = PendingStore(icons)
        self.tv.set_model(store)
    def _on_button_pressed(self, widget, event):
        """button press handler to capture clicks on the cancel button"""
        #print "_on_clicked: ", event
        if event == None or event.button != 1:
            return
        res = self.tv.get_path_at_pos(int(event.x), int(event.y))
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
        model = self.tv.get_model()
        if model[path][PendingStore.COL_CANCEL] == "":
            return 
        # get tid
        tid = model[path][PendingStore.COL_TID]
        trans = self._transactions_watcher.get_transaction(tid)
        try:
            trans.cancel()
        except dbus.exceptions.DBusException:
            logging.exception("transaction cancel failed")

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
