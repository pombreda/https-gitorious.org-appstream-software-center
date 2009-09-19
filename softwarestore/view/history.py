# Copyright (C) 2009 Canonical
#
# Authors:
#  Andrew Higginson
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

import gobject
import gtk
import os
import time
import logging
import pango

from random import *
import xml.etree.ElementTree as ET

HISTORY_FILE = "/tmp/history.xml"

class PkgHistory():
    """ reads/writes software-store's history """
    def __init__(self):
        self.history_root = None
    
    def open(self):
        """ open the history file for reading """
        try:
            tree = ET.parse(HISTORY_FILE)
        except Exception, e:
            logging.info("Error occured with parsing the history file %s " % e) 
            history = ET.Element("history")
            events = ET.SubElement(history, "events")
            tree = ET.ElementTree(history)
            tree.write(HISTORY_FILE)
            tree = ET.parse(HISTORY_FILE)
    
        self.history_root = tree.getroot()
    
    def add_event(self):
        events = self.history_root.find("events")
        new_event = ET.SubElement(events, "event")
        event_id = str(uniform(1, 100))
        new_event.set("id", event_id)
        new_event.set("time", str(time.time()))
        return event_id
        
    def add_action(self, event_id, type, package_name):
        events = self.history_root.find("events")
        for e in events.getchildren():
            if e.get("id") == event_id:
                event = e
        new_action = ET.SubElement(event, "action")
        new_action.set("type", type)
        new_action.set("package_name", package_name)
        
    def write(self):
        ET.ElementTree(self.history_root).write(HISTORY_FILE)
        

class HistoryView(gtk.TreeView):
    """Treeview based view component that takes a parsed history file and displays it"""

    """__gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
    }"""

    def __init__(self, store=None):
        gtk.TreeView.__init__(self)
        self.set_fixed_height_mode(True)
        self.set_headers_visible(False)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        column = gtk.TreeViewColumn("Name", tr)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        if store is None:
            store = gtk.ListStore(str, gtk.gdk.Pixbuf)
        self.set_model(store)
        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated)
        # button and motion are "special" 
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("motion-notify-event", self._on_motion_notify_event)
        self.connect("cursor-changed", self._on_cursor_changed)
    def _on_row_activated(self, treeview, path, column):
        (name, text, icon, overlay, pkgname) = treeview.get_model()[path]
        self.emit("application-activated", name, pkgname)
    def _on_cursor_changed(self, treeview):
        selection = treeview.get_selection()
        (model, iter) = selection.get_selected()
        if iter is None:
            return
        (name, text, icon, overlay, pkgname) = model[iter]
        self.emit("application-selected", name, pkgname)
    def _on_motion_notify_event(self, widget, event):
        (rel_x, rel_y, width, height, depth) = widget.window.get_geometry()
        if width - event.x <= AppStore.ICON_SIZE:
            self.window.set_cursor(self._cursor_hand)
        else:
            self.window.set_cursor(None)
    def _on_button_press_event(self, widget, event):
        if event.button != 1:
            return
        res = self.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        if path is None:
            return
        # only act when the selection is already there 
        selection = widget.get_selection()
        if not selection.path_is_selected(path):
            return
        # get the size of gdk window
        (rel_x, rel_y, width, height, depth) = widget.window.get_geometry()
        # the last pixels of the view are reserved for the arrow icon
        if width - event.x <= AppStore.ICON_SIZE:
            self.emit("row-activated", path, column)


if __name__ == "__main__":
    history = PkgHistory()
    history.open()
    event_id = history.add_event()
    history.add_action(event_id, "install", "gnome-games")
    history.add_action(event_id, "install", "gnome-chess")
    history.write()
    
    # gui
    scroll = gtk.ScrolledWindow()
    view = HistoryView()

    entry = gtk.Entry()
    #entry.connect("changed", on_entry_changed, (cache, db, view))

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    #scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()

