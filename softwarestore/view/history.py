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
import datetime
import logging
import pango

from gettext import gettext as _

from random import *
import xml.etree.ElementTree as ET

ICON_SIZE = 24
MISSING_APP_ICON = "/usr/share/icons/gnome/scalable/categories/applications-other.svg"
HISTORY_FILE = "/tmp/history.xml"

class History():
    """ reads/writes software-store's history """
    def __init__(self):
        self.history_root = None
    
    def _open(self):
        """ open the history file for reading/create if neccessary/corrupted """
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
    
    def add_event(self, type, package_name):
        self._open()
        events = self.history_root.find("events")
        new_event = ET.SubElement(events, "event")
        event_id = str(round(uniform(1, 100000000)))[:-2]
        new_event.set("id", event_id)
        new_event.set("date", str(datetime.date.today()))
        new_event.set("type", type)
        new_event.set("package_name", package_name)
        self._write()
        return event_id
        
    def add_action(self, event_id, type, package_name):
        self._open()
        events = self.history_root.find("events")
        for e in events.getchildren():
            if e.get("id") == event_id:
                event = e
        new_action = ET.SubElement(event, "action")
        new_action.set("type", type)
        new_action.set("package_name", package_name)
        self._write()
        
    def list_events(self):
        self._open()
        events = self.history_root.find("events")
        return events.getchildren()
        
    def _write(self):
        ET.ElementTree(self.history_root).write(HISTORY_FILE)
        

class HistoryStore(gtk.TreeView):
    """Treeview based view component that takes a parsed history file and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
    }

    def __init__(self, store=None):
        gtk.TreeView.__init__(self)
        self.set_fixed_height_mode(True)
        self.set_headers_visible(False)
        
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=0)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        column = gtk.TreeViewColumn("Name", tr, markup=1)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        self.store = gtk.ListStore(gtk.gdk.Pixbuf, str)
        
        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        self.show()

    def on_day_selected(self, calendar):
        (year, month, day) = calendar.get_date()
        if len(str(month)) == 1:
            month = "0" + str(month+1)
        else:
            month=+1
        if len(str(day)) == 1:
            day = "0" + str(day)
        date = str(year) + "-" + str(month) + "-" + str(day)
        self.populate(date_filter=date)
    def on_month_changed(self, calendar):
        self.update_highlighted(calendar)
    def update_highlighted(self, calendar):
        for r in range(31):
            calendar.unmark_day(int(r))
        (calendar_day, calendar_month, calendar_year) = calendar.get_date()
        calendar_month+=1
        events = history.list_events()
        for event in events:
            month = str(event.get("date"))[5:-3]
            day = str(event.get("date"))[-2:]
            if len(str(calendar_month)) == 1:
                calendar_month = "0" + str(calendar_month)
            if str(calendar_month) == month:
                calendar.mark_day(int(day))
    def populate(self, widget=None, date_filter=None):
        self.store.clear()
        self.set_model(self.store)
        history = History()
        events = history.list_events()
        for event in events:
            if event.get("type") == "install":
                type = _("installed")
            elif event.get("type") == "uninstall":
                type = _("uninstalled")
            if (date_filter and date_filter == event.get("date")) or not date_filter:
                s = "%s\n<small>" % event.get("package_name") + _("Was %s on") % type + " %s</small>" % event.get("date")
                pix = gtk.gdk.pixbuf_new_from_file_at_size(MISSING_APP_ICON, ICON_SIZE, ICON_SIZE)
                self.store.append([pix, s])
                
class HistoryView(gtk.VPaned):
    """Treeview based view component that takes a parsed history file and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, str, ),
                                  ),
    }

    def __init__(self, HistoryStore):
        gtk.VPaned.__init__(self)
        
        calendar = gtk.Calendar()
        self.add1(HistoryStore)
        self.add2(calendar)
        self.show()


if __name__ == "__main__":
    history = History()
    event_id = history.add_event("install", "gnome-games")
    history.add_action(event_id, "install", "gnome-games")
    history.add_action(event_id, "install", "gnome-chess")

    # gui
    scroll = gtk.ScrolledWindow()
    scroll.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
    view = HistoryView()
    
    view.populate()

    calendar = gtk.Calendar()
    calendar.connect("day-selected", view.on_day_selected)
    calendar.connect("month-changed", view.on_month_changed)

    vpane = gtk.VPaned()
    
    box = gtk.VBox()
    box.pack_start(vpane)
    vpane.add1(scroll)
    vpane.add2(calendar)

    win = gtk.Window()
    
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()
    win.connect('delete-event', lambda *x: gtk.main_quit())
    view.update_highlighted(calendar)

    gtk.main()

