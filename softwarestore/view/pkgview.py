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
        model = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("icon", tp, pixbuf=0)
        self.append_column(column)
        tr = gtk.CellRendererText()
        column = gtk.TreeViewColumn(header, tr, markup=1)
        self.append_column(column)
        for pkg in sorted(pkgnames):
            s = "%s \n<small>%s</small>" % (cache[pkg].installed.summary, pkg)
            pix = gtk.gdk.pixbuf_new_from_file("/usr/share/icons/gnome/scalable/categories/applications-other.svg")
            model.append([pix, s])


