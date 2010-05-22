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


import gobject
import gio
import glib
import gtk

import apt_pkg
apt_pkg.init_config()

from debian_bundle import deb822

import os.path
import datetime

from gettext import gettext as _

from softwarecenter.enums import *
from softwarecenter.view.widgets.searchentry import SearchEntry
from softwarecenter.apt.aptcache import AptCache
from softwarecenter.db.database import StoreDatabase


class HistoryPane(gtk.VBox):

    __gsignals__ = {
        "app-list-changed" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (int, ),
                             ),
    }

    (COL_WHEN, COL_ACTION, COL_PKG) = range(3)
    COL_TYPES = (object, int, str)

    (ALL, INSTALLED, REMOVED) = range(3)

    ICON_SIZE = 24
    PADDING = 6

    def __init__(self, cache, history, db, distro, icons, datadir):
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

        installs_action = gtk.RadioAction('filter_installs', _('All Installations'), None, None, self.INSTALLED)
        installs_action.set_group(all_action)
        installs_button = installs_action.create_tool_item()
        self.toolbar.insert(installs_button, 1)

        removals_action = gtk.RadioAction('filter_removals', _('All Removals'), None, None, self.REMOVED)
        removals_action.set_group(all_action)
        removals_button = removals_action.create_tool_item()
        self.toolbar.insert(removals_button, 2)

        self.view = gtk.TreeView()
        self.view.show()
        self.scrolled_view = gtk.ScrolledWindow()
        self.scrolled_view.set_policy(gtk.POLICY_AUTOMATIC,
                                      gtk.POLICY_AUTOMATIC)
        self.scrolled_view.show()
        self.scrolled_view.add(self.view)
        self.pack_start(self.scrolled_view)

        self.store = gtk.TreeStore(*self.COL_TYPES)
        self.visible_changes = 0
        self.store_filter = self.store.filter_new()
        self.store_filter.set_visible_func(self.filter_row)
        self.view.set_model(self.store_filter)
        all_action.set_active(True)
        self.filename = apt_pkg.config.find_file("Dir::Log::History")
        self.last = None
        
        self.history = history
        self.parse_history()
        self.history.set_on_update(self.parse_history)
        

        self.column = gtk.TreeViewColumn(_('Date'))
        self.view.append_column(self.column)
        self.cell_icon = gtk.CellRendererPixbuf()
        self.column.pack_start(self.cell_icon, False)
        self.column.set_cell_data_func(self.cell_icon, self.render_cell_icon)
        self.cell_text = gtk.CellRendererText()
        self.column.pack_start(self.cell_text)
        self.column.set_cell_data_func(self.cell_text, self.render_cell_text)

    def _reset_icon_cache(self, theme=None):
        self._app_icon_cache.clear()
        try:
            missing = self.icons.load_icon(MISSING_APP_ICON, self.ICON_SIZE, 0)
        except glib.GError:
            missing = None
        self._app_icon_cache[MISSING_APP_ICON] = missing

    def parse_history(self):
        print "parse history"
        date = None
        last_row = None
        day = self.store.get_iter_first()
        if day is not None:
            date = self.store.get_value(day, self.COL_WHEN)
        new_last = self.history.transactions[0].start_date
        for trans in self.history.transactions:
            when = trans.start_date
            if self.last is not None and when <= self.last:
                break
            if when.date() != date:
                date = when.date()
                day = self.store.append(None, (date, self.ALL, None))
                last_row = None
            actions = {self.INSTALLED: trans.install, self.REMOVED: trans.remove}
            for action, pkgs in actions.iteritems():
                pkgnames = [p.split()[0] for p in pkgs]
                for pkgname in pkgnames:
                    row = (when, action, pkgname)
                    last_row = self.store.insert_after(day, last_row, row)
        self.last = new_last
        self.update_view()

    def is_category_view_showing(self):
        # There is no category view in the installed pane.
        return False

    def update_app_view(self):
        # TODO
        pass

    def get_status_text(self):
        return _('%d changes') % self.visible_changes

    def on_search_terms_changed(self, entry, terms):
        self.update_view()

    def get_current_app(self):
        return None

    def change_filter(self, action, current):
        self.filter = action.get_current_value()
        self.update_view()

    def update_view(self):
        self.store_filter.refilter()

        # Expand all the matching rows
        if self.searchentry.get_text():
            self.view.expand_all()

        # Compute the number of visible changes
        self.visible_changes = 0
        day = self.store_filter.get_iter_first()
        while day is not None:
            self.visible_changes += self.store_filter.iter_n_children(day)
            day = self.store_filter.iter_next(day)

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
            icon_name = MISSING_APP_ICON
            for m in self.db.xapiandb.postlist("AP" + pkg):
                doc = self.db.xapiandb.get_document(m.docid)
                icon_value = doc.get_value(XAPIAN_VALUE_ICON)
                if icon_value:
                    icon_name = os.path.splitext(icon_value)[0]
                break
            if icon_name in self._app_icon_cache:
                icon = self._app_icon_cache[icon_name]
            else:
                try:
                    icon = self.icons.load_icon(icon_name, self.ICON_SIZE, 0)
                except glib.GError:
                    icon = self._app_icon_cache[MISSING_APP_ICON]
                self._app_icon_cache[icon_name] = icon
            cell.set_property('pixbuf', icon)

    def render_cell_text(self, column, cell, store, iter):
        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            pkg = store.get_value(iter, self.COL_PKG)
            if action == self.INSTALLED:
                text = _('%s installed %s') % (pkg, when.time().strftime('%X'))
            elif action == self.REMOVED:
                text = _('%s removed %s') % (pkg, when.time().strftime('%X'))
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
    cache = AptCache()

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
    window.connect('destroy', gtk.main_quit)

    gtk.main()

