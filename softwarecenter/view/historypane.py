# Copyright (C) 2009 Canonical
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
import gtk

import apt_pkg
apt_pkg.init_config()

from debian_bundle import deb822

import datetime

from gettext import gettext as _


class HistoryPane(gtk.VBox):

    __gsignals__ = {
        "app-list-changed" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (int, ),
                             ),
    }

    (COL_WHEN, COL_ACTION, COL_APP) = range(3)
    COL_TYPES = (object, int, str)

    (ALL, INSTALLED, REMOVED) = range(3)

    def __init__(self, cache, db, distro, icons, datadir):
        gtk.VBox.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir

        self.apps_filter = None

        self.toolbar = gtk.Toolbar()
        self.toolbar.show()
        self.toolbar.set_style(gtk.TOOLBAR_TEXT)
        self.pack_start(self.toolbar, False)

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
        self.filename = apt_pkg.Config.FindFile("Dir::Log::History")
        self.last = None
        self.parse_history_log()

        self.logfile = gio.File(self.filename)
        self.monitor = self.logfile.monitor_file()
        self.monitor.connect("changed", self._on_apt_history_changed)

        self.column = gtk.TreeViewColumn(_('Date'))
        self.view.append_column(self.column)
        self.cell = gtk.CellRendererText()
        self.column.pack_start(self.cell)
        self.column.set_cell_data_func(self.cell, self.render_cell)

    def _on_apt_history_changed(self, monitor, afile, other_file, event):
        if event == gio.FILE_MONITOR_EVENT_CHANGES_DONE_HINT:
            self.parse_history_log()

    def parse_history_log(self):
        actions = {self.INSTALLED: 'Install', self.REMOVED: 'Remove'}
        fd = open(self.filename)
        date = None
        day = self.store.get_iter_first()
        if day is not None:
            date = self.store.get_value(day, self.COL_WHEN)
        for stanza in deb822.Deb822.iter_paragraphs(fd):
            when = datetime.datetime.strptime(stanza['Start-Date'], '%Y-%m-%d %H:%M:%S')
            if self.last is not None and when <= self.last:
                continue
            for action, key in actions.iteritems():
                if not stanza.has_key(key):
                    continue
                if when.date() != date:
                    date = when.date()
                    day = self.store.prepend(None, (date, self.ALL, None))
                packages = stanza[key].split(', ')
                # Drop the version numbers
                pkgnames = [p.split()[0] for p in packages]
                for pkgname in pkgnames:
                    row = (when, action, pkgname)
                    self.store.append(day, row)

        fd.close()
        self.last = when
        self.update_view()

    def is_category_view_showing(self):
        # There is no category view in the installed pane.
        return False

    def update_app_view(self):
        # TODO
        pass

    def get_status_text(self):
        return _('%d changes') % self.visible_changes

    def get_current_app(self):
        return None

    def change_filter(self, action, current):
        self.filter = action.get_current_value()
        self.update_view()

    def update_view(self):
        self.store_filter.refilter()

        # Compute the number of visible changes
        self.visible_changes = 0
        day = self.store_filter.get_iter_first()
        while day is not None:
            self.visible_changes += self.store_filter.iter_n_children(day)
            day = self.store_filter.iter_next(day)

        self.emit('app-list-changed', self.visible_changes)

    def filter_row(self, store, iter):
        if self.filter == self.ALL:
            return True
        elif not store.iter_has_child(iter):
            return (self.filter == store.get_value(iter, self.COL_ACTION))
        else:
            i = store.iter_children(iter)
            while i is not None:
                if store.get_value(i, self.COL_ACTION) == self.filter:
                    return True
                i = store.iter_next(i)
            return False

    def render_cell(self, column, cell, store, iter):
        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            app = store.get_value(iter, self.COL_APP)
            if action == self.INSTALLED:
                text = _('%s installed %s') % (app, when.time().strftime('%X'))
            elif action == self.REMOVED:
                text = _('%s removed %s') % (app, when.time().strftime('%X'))
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
    widget = HistoryPane(None, None, None, None, None)
    widget.show()

    window = gtk.Window()
    window.add(widget)
    window.set_size_request(600, 500)
    window.set_position(gtk.WIN_POS_CENTER)
    window.show_all()
    window.connect('destroy', gtk.main_quit)

    gtk.main()

