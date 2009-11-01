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
import glib
import gobject
import gtk
import logging
import xapian
import os

# magic environment to get new pathbar
if "SOFTWARE_CENTER_NEW_PATHBAR" in os.environ:
    from widgets.pathbar2 import NavigationBar
else:
    from widgets.navigationbar import NavigationBar

from widgets.searchentry import SearchEntry

from appview import AppView, AppStore, AppViewFilter
from appdetailsview import AppDetailsView


def wait_for_apt_cache_ready(f):
    """ decorator that ensures that the cache is ready using a
        gtk idle_add - needs a cache as argument
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        # check if the cache is ready and 
        if not self.cache.ready:
            if self.app_view.window:
                self.app_view.window.set_cursor(self.busy_cursor)
            glib.timeout_add(500, lambda: wrapper(*args, **kwargs))
            return False
        # cache ready now
        if self.app_view.window:
            self.app_view.window.set_cursor(None)
        f(*args, **kwargs)
        return False
    return wrapper
            

class SoftwarePane(gtk.VBox):
    """ Common base class for InstalledPane and AvailablePane """

    __gsignals__ = {
        "app-list-changed" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (int, ),
                             )
    }
    PADDING = 6

    def __init__(self, cache, db, icons, datadir):
        gtk.VBox.__init__(self)
        # other classes we need
        self.cache = cache
        self.db = db
        self.db.connect("reopen", self.on_db_reopen)
        self.icons = icons
        self.datadir = datadir
        # common UI elements (applist and appdetails) 
        # its the job of the Child class to put it into a good location
        # list
        self.app_view = AppView()
        self.scroll_app_list = gtk.ScrolledWindow()
        self.scroll_app_list.set_policy(gtk.POLICY_AUTOMATIC, 
                                        gtk.POLICY_AUTOMATIC)
        self.scroll_app_list.add(self.app_view)
        # details
        self.app_details = AppDetailsView(self.db, 
                                          self.icons, 
                                          self.cache, 
                                          self.datadir)
        self.scroll_details = gtk.ScrolledWindow()
        self.scroll_details.set_policy(gtk.POLICY_AUTOMATIC, 
                                       gtk.POLICY_AUTOMATIC)
        self.scroll_details.add(self.app_details)
        # cursor
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
        # when the cache changes, refresh the app list
        self.cache.connect("cache-ready", self.on_cache_ready)
        # COMMON UI elements
        # navigation bar and search on top in a hbox
        self.navigation_bar = NavigationBar()
        self.searchentry = SearchEntry()
        self.searchentry.connect("terms-changed", self.on_search_terms_changed)
        top_hbox = gtk.HBox()
        top_hbox.pack_start(self.navigation_bar, padding=self.PADDING)
        top_hbox.pack_start(self.searchentry, expand=False, padding=self.PADDING)
        self.pack_start(top_hbox, expand=False, padding=self.PADDING)
        # a notebook below
        self.notebook = gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        self.pack_start(self.notebook)

    def on_cache_ready(self, cache):
        " refresh the application list when the cache is re-opened "
        # FIXME: preserve selection too
        # get previous vadjustment and reapply it
        vadj = self.scroll_app_list.get_vadjustment()
        self.refresh_apps()
        # needed otherwise we jump back to the beginning of the table
        if vadj:
            vadj.value_changed()

    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        raise Exception, "Not implemented"

    @wait_for_apt_cache_ready
    def refresh_apps(self):
        " stub implementation "
        pass
    
    def on_search_terms_changed(self, terms):
        " stub implementation "
        pass

    def on_db_reopen(self):
        " stub implementation "
        pass
