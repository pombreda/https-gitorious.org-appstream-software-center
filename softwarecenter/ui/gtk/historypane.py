# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Canonical
#
# Authors:
#  Olivier Tilloy
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
# this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import GObject
from gi.repository import GObject
import gtk
import logging

import apt_pkg
apt_pkg.init_config()

import os.path
import datetime

from gettext import gettext as _

from widgets.searchentry import SearchEntry
from widgets.spinner import SpinnerView
from basepane import BasePane

from softwarecenter.enums import Icons, XapianValues
from softwarecenter.paths import ICON_PATH, XAPIAN_BASE_PATH
from softwarecenter.db.database import StoreDatabase

class HistoryPane(gtk.VBox, BasePane):

    __gsignals__ = {
        "app-list-changed" : (GObject.SIGNAL_RUN_LAST,
                              GObject.TYPE_NONE, 
                              (int, ),
                             ),
        "history-pane-created" : (GObject.SIGNAL_RUN_FIRST,
                                  GObject.TYPE_NONE,
                                  ()),
    }

    (COL_WHEN, COL_ACTION, COL_PKG) = range(3)
    COL_TYPES = (object, int, str)

    (ALL, INSTALLED, REMOVED, UPGRADED) = range(4)

    ICON_SIZE = 24
    PADDING = 6
    
    # pages for the spinner notebook
    (PAGE_HISTORY_VIEW,
     PAGE_SPINNER) = range(2)

    def __init__(self, cache, db, distro, icons, datadir):
        gtk.VBox.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir

        self.apps_filter = None

        # Icon cache, invalidated upon icon theme changes
        self._app_icon_cache = {}
        self._reset_icon_cache()
        self.icons.connect('changed', self._reset_icon_cache)

        self.header = gtk.HBox()
        self.header.show()
        self.pack_start(self.header, expand=False, padding=self.PADDING)

        self.title = gtk.Label()
        self.title.show()
        self.title.set_alignment(0, 0)
        self.title.set_markup(_('<span size="x-large">History</span>'))
        self.header.pack_start(self.title, padding=self.PADDING)

        self.searchentry = SearchEntry()
        self.searchentry.connect('terms-changed', self.on_search_terms_changed)
        self.searchentry.show()
        self.header.pack_start(self.searchentry, expand=False, padding=self.PADDING)

        self.pack_start(gtk.HSeparator(), expand=False)

        self.toolbar = gtk.Toolbar()
        self.toolbar.show()
        self.toolbar.set_style(gtk.TOOLBAR_TEXT)
        self.pack_start(self.toolbar, expand=False)

        all_action = gtk.RadioAction('filter_all', _('All Changes'), None, None, self.ALL)
        all_action.connect('changed', self.change_filter)
        all_button = all_action.create_tool_item()
        self.toolbar.insert(all_button, 0)

        installs_action = gtk.RadioAction('filter_installs', _('Installations'), None, None, self.INSTALLED)
        installs_action.set_group(all_action)
        installs_button = installs_action.create_tool_item()
        self.toolbar.insert(installs_button, 1)

        upgrades_action = gtk.RadioAction(
            'filter_upgrads', _('Updates'), None, None, self.UPGRADED)
        upgrades_action.set_group(all_action)
        upgrades_button = upgrades_action.create_tool_item()
        self.toolbar.insert(upgrades_button, 2)

        removals_action = gtk.RadioAction(
            'filter_removals', _('Removals'), None, None, self.REMOVED)
        removals_action.set_group(all_action)
        removals_button = removals_action.create_tool_item()
        self.toolbar.insert(removals_button, 3)
        
        self._actions_list = all_action.get_group()
        self._set_actions_sensitive(False)

        self.view = gtk.TreeView()
        self.view.show()
        self.history_view = gtk.ScrolledWindow()
        self.history_view.set_policy(gtk.POLICY_AUTOMATIC,
                                      gtk.POLICY_AUTOMATIC)
        self.history_view.show()
        self.history_view.add(self.view)
        
        # make a spinner to display while history is loading
        self.spinner_view = SpinnerView(_('Loading history'))
        self.spinner_notebook = gtk.Notebook()
        self.spinner_notebook.set_show_tabs(False)
        self.spinner_notebook.set_show_border(False)
        self.spinner_notebook.append_page(self.history_view)
        self.spinner_notebook.append_page(self.spinner_view)
        
        self.pack_start(self.spinner_notebook)

        self.store = gtk.TreeStore(*self.COL_TYPES)
        self.visible_changes = 0
        self.store_filter = self.store.filter_new()
        self.store_filter.set_visible_func(self.filter_row)
        self.view.set_model(self.store_filter)
        all_action.set_active(True)
        self.filename = apt_pkg.config.find_file("Dir::Log::History")
        self.last = None
        
        # to save (a lot of) time at startup we load history later, only when
        # it is selected to be viewed
        self.history = None

        self.column = gtk.TreeViewColumn(_('Date'))
        self.view.append_column(self.column)
        self.cell_icon = gtk.CellRendererPixbuf()
        self.column.pack_start(self.cell_icon, False)
        self.column.set_cell_data_func(self.cell_icon, self.render_cell_icon)
        self.cell_text = gtk.CellRendererText()
        self.column.pack_start(self.cell_text)
        self.column.set_cell_data_func(self.cell_text, self.render_cell_text)
        
        # busy cursor
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
        
    def init_view(self):
        if self.history == None:
            # if the history is not yet initialized we have to load and parse it
            # show a spinner while we do that
            self.window.set_cursor(self.busy_cursor)
            self.spinner_view.start()
            self.spinner_notebook.set_current_page(self.PAGE_SPINNER)
            self.load_and_parse_history()
            self.spinner_notebook.set_current_page(self.PAGE_HISTORY_VIEW)
            self.spinner_view.stop()
            self._set_actions_sensitive(True)
            self.window.set_cursor(None)
            self.emit("history-pane-created")
            
    def _set_actions_sensitive(self, sensitive):
        for action in self._actions_list:
            action.set_sensitive(sensitive)

    def _reset_icon_cache(self, theme=None):
        self._app_icon_cache.clear()
        try:
            missing = self.icons.load_icon(Icons.MISSING_APP, self.ICON_SIZE, 0)
        except GObject.GError:
            missing = None
        self._app_icon_cache[Icons.MISSING_APP] = missing
        
    def load_and_parse_history(self):
        from softwarecenter.db.history import get_pkg_history
        self.history = get_pkg_history()
        # FIXME: a signal from AptHistory is nicer
        while not self.history.history_ready:
            while gtk.events_pending():
                gtk.main_iteration()
        self.parse_history()
        self.history.set_on_update(self.parse_history)

    def parse_history(self):
        date = None
        when = None
        last_row = None
        day = self.store.get_iter_first()
        if day is not None:
            date = self.store.get_value(day, self.COL_WHEN)
        if len(self.history.transactions) == 0:
            logging.debug("AptHistory is currently empty")
            return
        new_last = self.history.transactions[0].start_date
        for trans in self.history.transactions:
            while gtk.events_pending():
                gtk.main_iteration()
            when = trans.start_date
            if self.last is not None and when <= self.last:
                break
            if when.date() != date:
                date = when.date()
                day = self.store.append(None, (date, self.ALL, None))
                last_row = None
            actions = {self.INSTALLED: trans.install, 
                       self.REMOVED: trans.remove,
                       self.UPGRADED: trans.upgrade,
                      }
            for action, pkgs in actions.iteritems():
                for pkgname in pkgs:
                    row = (when, action, pkgname)
                    last_row = self.store.insert_after(day, last_row, row)
        self.last = new_last
        self.update_view()

    def get_status_text(self):
        return _('%d changes') % self.visible_changes

    def on_search_terms_changed(self, entry, terms):
        self.update_view()

    def change_filter(self, action, current):
        self.filter = action.get_current_value()
        self.update_view()

    def update_view(self):
        self.store_filter.refilter()
        self.view.collapse_all()
        # Expand all the matching rows
        if self.searchentry.get_text():
            self.view.expand_all()

        # Compute the number of visible changes
        self.visible_changes = 0
        day = self.store_filter.get_iter_first()
        while day is not None:
            self.visible_changes += self.store_filter.iter_n_children(day)
            day = self.store_filter.iter_next(day)
            
        # Expand the most recent day
        day = self.store.get_iter_first()
        if day is not None:
	        path = self.store.get_path(day)
	        self.view.expand_row(path, False)
	        self.view.scroll_to_cell(path)

        self.emit('app-list-changed', self.visible_changes)

    def _row_matches(self, store, iter):
        # Whether a child row matches the current filter and the search entry
        pkg = store.get_value(iter, self.COL_PKG) or ''
        filter_values = (self.ALL, store.get_value(iter, self.COL_ACTION))
        filter_matches = self.filter in filter_values
        search_matches = self.searchentry.get_text().lower() in pkg.lower()
        return filter_matches and search_matches

    def filter_row(self, store, iter):
        pkg = store.get_value(iter, self.COL_PKG)
        if pkg is not None:
            return self._row_matches(store, iter)
        else:
            i = store.iter_children(iter)
            while i is not None:
                if self._row_matches(store, i):
                    return True
                i = store.iter_next(i)
            return False

    def render_cell_icon(self, column, cell, store, iter):
        pkg = store.get_value(iter, self.COL_PKG)
        if pkg is None:
            cell.set_visible(False)
        else:
            cell.set_visible(True)
            icon_name = Icons.MISSING_APP
            for m in self.db.xapiandb.postlist("AP" + pkg):
                doc = self.db.xapiandb.get_document(m.docid)
                icon_value = doc.get_value(XapianValues.ICON)
                if icon_value:
                    icon_name = os.path.splitext(icon_value)[0]
                break
            if icon_name in self._app_icon_cache:
                icon = self._app_icon_cache[icon_name]
            else:
                try:
                    icon = self.icons.load_icon(icon_name, self.ICON_SIZE, 0)
                except GObject.GError:
                    icon = self._app_icon_cache[Icons.MISSING_APP]
                self._app_icon_cache[icon_name] = icon
            cell.set_property('pixbuf', icon)

    def render_cell_text(self, column, cell, store, iter):
        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            pkg = store.get_value(iter, self.COL_PKG)
	    # Translators : time displayed in history, display hours (0-12), minutes and AM/PM. %H should be used instead of %I to display hours 0-24
            subs = {'pkgname': pkg, 'time': when.time().strftime(_('%I:%M %p'))}
            if action == self.INSTALLED:
                text = _('%(pkgname)s installed %(time)s') % subs
            elif action == self.REMOVED:
                text = _('%(pkgname)s removed %(time)s') % subs
            elif action == self.UPGRADED:
                text = _('%(pkgname)s updated %(time)s') % subs
        elif isinstance(when, datetime.date):
            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            if when >= monday:
                # Current week, display the name of the day
                text = when.strftime(_('%A'))
            else:
                if when.year == today.year:
                    # Current year, display the day and month
                    text = when.strftime(_('%d %B'))
                else:
                    # Display the full date: day, month, year
                    text = when.strftime(_('%d %B %Y'))
        cell.set_property('text', text)


if __name__ == '__main__':
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()

    db_path = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = StoreDatabase(db_path, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path(ICON_PATH)

    widget = HistoryPane(cache, db, None, icons, None)
    widget.show()

    window = gtk.Window()
    window.add(widget)
    window.set_size_request(600, 500)
    window.set_position(gtk.WIN_POS_CENTER)
    window.show_all()
    widget.init_view()
    window.connect('destroy', gtk.main_quit)

    gtk.main()

