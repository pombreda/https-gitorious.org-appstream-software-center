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

from softwarecenter.enums import *
from softwarecenter.db.database import StoreDatabase
from softwarecenter.backend.transactionswatcher import TransactionsWatcher
from widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage

class ViewSwitcher(gtk.TreeView):

    __gsignals__ = {
        "view-changed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (int, str),
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
        
        self.set_model(store)
        self.set_headers_visible(False)
        self.get_selection().set_select_function(self.on_treeview_selected)
        # expand the first entry (get software)
        self.expand_to_path((0,))
        self.set_level_indentation(4)
        self.set_enable_search(False)
        
        self.connect("row-expanded", self.on_treeview_row_expanded)
        self.connect("row-collapsed", self.on_treeview_row_collapsed)
        self.connect("cursor-changed", self.on_cursor_changed)
        
    def on_treeview_row_expanded(self, widget, iter, path):
        #behaviour overrides
        pass
        
    def on_treeview_row_collapsed(self, widget, iter, path):
        #behaviour overrides
        pass
    
    def on_treeview_selected(self, path):
        if path[0] == ViewSwitcherList.ACTION_ITEM_SEPARATOR_1:
            return False
        return True
        
    def on_cursor_changed(self, widget):
        (path, column) = self.get_cursor()
        model = self.get_model()
        action = model[path][ViewSwitcherList.COL_ACTION]
        self.emit("view-changed", action) 
        
    def get_view(self):
        """return the current activated view number or None if no
           view is activated (this can happen when a pending view 
           disappeared). Views are:
           
           ViewSwitcherList.ACTION_ITEM_AVAILABLE
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

class ViewSwitcherList(gtk.TreeStore, TransactionsWatcher):
    
    # columns
    (COL_ICON,
     COL_NAME,
     COL_ACTION,
     COL_ACTION_DETAILS) = range(4)

    # items in the treeview
    (ACTION_ITEM_AVAILABLE,
     ACTION_ITEM_INSTALLED,
     ACTION_ITEM_SEPARATOR_1,
     ACTION_ITEM_PENDING,
     ACTION_PPA_SOURCE_VIEW) = range(5)

    ICON_SIZE = 24

    ANIMATION_PATH = "/usr/share/icons/hicolor/24x24/status/softwarecenter-progress.png"

    __gsignals__ = {'transactions-changed' : (gobject.SIGNAL_RUN_LAST,
                                              gobject.TYPE_NONE,
                                              (int, )),
                     }

    def __init__(self, datadir, db, icons):
        gtk.TreeStore.__init__(self, AnimatedImage, str, int, str)
        TransactionsWatcher.__init__(self)
        self.icons = icons
        self.datadir = datadir
        self.db = db
        # pending transactions
        self._pending = 0
        # setup the normal stuff
        root_icon = self._get_icon("softwarecenter")
        piter = self.append(None, [root_icon, _("Get Software"), self.ACTION_ITEM_AVAILABLE, None])
        
        dist_icon = self._get_icon("distributor-logo")
        ppa_icon = self._get_icon("ppa")
        partner_icon = self._get_icon("partner")
        
        # append additional sources
        source_labels = []
        for it in self.db.xapiandb.allterms("XOL"):
            term = it.term[3:]            
            print term
            

            m = db.xapiandb.postlist_begin(it.term)
            doc = db.xapiandb.get_document(m.get_docid())
            for term_it in doc.termlist():
                if term_it.term.startswith("XOOLP-PPA-"): 
                    print "yup, it's a ppa"
                    break
                
            if term == "Ubuntu":       # lose this, sort list properly per below
                print "!"
                source_labels.insert(0, term)
            else:
                source_labels.append(term)
                
       
        
            
        # TODO: sort and arrange sources: Ubuntu, Partners, PPAs alphabetically, Unknown source last
        # TODO: determine icon per source and associate it
        
        # add the source items
        for label in source_labels:
            print "append source with label: %s" % label
            
            if label == "Ubuntu":         # lose this, better way to associate the icon
                source_icon = dist_icon
            else:
                source_icon = ppa_icon
                
            if not label:
                label_str = "Unknown"
            elif label == "Ubuntu":
                label_str = _("Provided by Ubuntu")
            else:
                label_str = label
            self.append(piter, [source_icon, label_str, self.ACTION_PPA_SOURCE_VIEW, label])
        
        icon = AnimatedImage(self.icons.load_icon("computer", self.ICON_SIZE, 0))
        self.append(None, [icon, _("Installed Software"), self.ACTION_ITEM_INSTALLED, ""])
        icon = AnimatedImage(None)
        self.append(None, [icon, "<span size='1'> </span>", self.ACTION_ITEM_SEPARATOR_1, ""])

    def on_transactions_changed(self, current, queue):
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
                self.append(None, [icon, _("In Progress (%i)") % pending, 
                             self.ACTION_ITEM_PENDING])
        else:
            for (i, row) in enumerate(self):
                if row[self.COL_ACTION] == self.ACTION_ITEM_PENDING:
                    del self[(i,)]
        # emit signal
        if pending != self._pending:
            self.emit("transactions-changed", pending)
            self._pending = pending
        return True
        
    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon

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
