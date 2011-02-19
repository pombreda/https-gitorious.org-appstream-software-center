# Copyright (C) 2011 Canonical
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

import gtk
import logging
import pango

from softwarecenter.db.application import Application
from softwarecenter.enums import MISSING_APP_ICON

LOG = logging.getLogger(__name__)

class PackageNamesView(gtk.TreeView):
    """ A simple widget that presents a list of packages, with
        associated icons, in a treeview.  Note the for current
        uses we only show installed packages.  Useful in dialogs.
    """
    (COL_ICON,
     COL_TEXT) = range(2)

    def __init__(self, header, cache, pkgnames, icons, icon_size, db):
        super(PackageNamesView, self).__init__()
        model = gtk.ListStore(gtk.gdk.Pixbuf, str)
        self.set_model(model)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=self.COL_ICON)
        self.append_column(column)
        tr = gtk.CellRendererText()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn(header, tr, markup=self.COL_TEXT)
        self.append_column(column)
        for pkgname in sorted(pkgnames):
            if (not pkgname in cache or
                not cache[pkgname].installed):
                continue
            s = "%s \n<small>%s</small>" % (
                cache[pkgname].installed.summary.capitalize(), pkgname)
            
            app_details = Application("", pkgname).get_details(db)
            proposed_icon = app_details.icon
            if not proposed_icon or not icons.has_icon(proposed_icon):
                proposed_icon = MISSING_APP_ICON
            try:
                pix = icons.load_icon(proposed_icon, icon_size, ()).scale_simple(icon_size, 
                                      icon_size, gtk.gdk.INTERP_BILINEAR)
            except:
                LOG.warning("cant set icon for '%s' " % pkgname)
                pix = icons.load_icon(MISSING_APP_ICON, icon_size, ()).scale_simple(icon_size, 
                                      icon_size, gtk.gdk.INTERP_BILINEAR)
            row = model.append([pix, s])
            
        # finally, we don't allow selection, it's just a simple display list
        tree_selection = self.get_selection()
        tree_selection.set_mode(gtk.SELECTION_NONE)
