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


class HistoryPane(gtk.VBox):

    def __init__(self, cache, db, distro, icons, datadir):
        gtk.VBox.__init__(self)
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir

        self.apps_filter = None

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

