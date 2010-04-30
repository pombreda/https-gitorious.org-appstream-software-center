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


import gtk

import apt_pkg
apt_pkg.init_config()

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
        self.pack_start(self.view)

        self.store = gtk.TreeStore(*self.COL_TYPES)
        self.populate_store()
        self.view.set_model(self.store)

        self.column = gtk.TreeViewColumn(_('Date'))
        self.view.append_column(self.column)
        self.cell = gtk.CellRendererText()
        self.column.pack_start(self.cell)
        self.column.set_cell_data_func(self.cell, self.render_cell)

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

    def populate_store(self):
        # re-populate store from scratch
        filename = apt_pkg.Config.FindFile("Dir::Log::History")
        fd = open(filename)
        tagfile = apt_pkg.ParseTagFile(fd)
        date = None
        day = None
        while tagfile.Step():
            section = tagfile.Section
            for action in (self.INSTALL, self.REMOVE):
                if section.has_key(action):
                    when = datetime.datetime.strptime(section['Start-Date'], '%Y-%m-%d %H:%M:%S')
                    packages = section[action].split(', ')
                    # Drop the version numbers
                    pkgnames = [p.split()[0] for p in packages]
                    for pkgname in pkgnames:
                        # FIXME: a package is not necessarily an application, we
                        # need to filter out those that are not.
                        row = (when, action, pkgname)
                        if when.date() != date:
                            date = when.date()
                            day = self.store.prepend(None, (date, None, None))
                        self.store.append(day, row)
        fd.close()

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

