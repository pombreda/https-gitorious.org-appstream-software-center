# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
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


import gtk

from gettext import gettext as _

class PkgNamesView(gtk.TreeView):
    """ show a bunch of pkgnames with description """
    def __init__(self, header, cache, pkgnames):
        super(PkgNamesView, self).__init__()
        model = gtk.ListStore(str)
        self.set_model(model)
        #self.set_headers_visible(False)
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn(header, tr, text=0)
        self.append_column(column)
        for pkg in sorted(pkgnames):
            s = "%s <br> <x-small>%s</x-small>" % (cache[pkg].installed.summary, pkg)
            model.append([s])


