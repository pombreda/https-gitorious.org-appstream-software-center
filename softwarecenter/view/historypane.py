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


import gio
import gtk

import apt_pkg
apt_pkg.init_config()

from debian_bundle import deb822

import datetime

from gettext import gettext as _


class HistoryPane(gtk.VBox):

    (COL_WHEN, COL_ACTION, COL_APP) = range(3)
    COL_TYPES = (object, str, str)

    INSTALL = 'Install'
    REMOVE = 'Remove'

    def __init__(self, cache, db, distro, icons, datadir):
        gtk.VBox.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir

        self.apps_filter = None

        self.view = gtk.TreeView()
        self.view.show()
        self.scrolled_view = gtk.ScrolledWindow()
        self.scrolled_view.set_policy(gtk.POLICY_AUTOMATIC,
                                      gtk.POLICY_AUTOMATIC)
        self.scrolled_view.show()
        self.scrolled_view.add(self.view)
        self.pack_start(self.scrolled_view)

        self.store = gtk.TreeStore(*self.COL_TYPES)
        self.view.set_model(self.store)
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
        fd = open(self.filename)
        date = None
        day = self.store.get_iter_first()
        if day is not None:
            date = self.store.get_value(day, self.COL_WHEN)
        for stanza in deb822.Deb822.iter_paragraphs(fd):
            when = datetime.datetime.strptime(stanza['Start-Date'], '%Y-%m-%d %H:%M:%S')
            if self.last is not None and when <= self.last:
                continue
            for action in (self.INSTALL, self.REMOVE):
                if not stanza.has_key(action):
                    continue
                if when.date() != date:
                    date = when.date()
                    day = self.store.prepend(None, (date, None, None))
                packages = stanza[action].split(', ')
                # Drop the version numbers
                pkgnames = [p.split()[0] for p in packages]
                for pkgname in pkgnames:
                    row = (when, action, pkgname)
                    self.store.append(day, row)

        fd.close()
        self.last = when

    def is_category_view_showing(self):
        # There is no category view in the installed pane.
        return False

    def update_app_view(self):
        # TODO
        pass

    def get_status_text(self):
        # TODO
        return ''

    def get_current_app(self):
        return None

    def render_cell(self, column, cell, store, iter):
        when = store.get_value(iter, self.COL_WHEN)
        if isinstance(when, datetime.datetime):
            action = store.get_value(iter, self.COL_ACTION)
            app = store.get_value(iter, self.COL_APP)
            if action == self.INSTALL:
                text = _('%s installed %s') % (app, when.time().strftime('%X'))
            elif action == self.REMOVE:
                text = _('%s removed %s') % (app, when.time().strftime('%X'))
        elif isinstance(when, datetime.date):
            text = when.strftime('%x')
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

