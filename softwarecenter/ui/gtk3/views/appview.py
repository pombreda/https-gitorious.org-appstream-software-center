# Copyright (C) 2009,2010 Canonical
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

#~ from __future__ import with_statement



from gi.repository import Gtk, GObject
from gettext import gettext as _

from softwarecenter.enums import SortMethods
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.apptreeview import AppTreeView
from softwarecenter.ui.gtk3.models.appstore2 import AppPropertiesHelper
from softwarecenter.ui.gtk3.widgets.containers import FlowableGrid


class AppView(Gtk.VBox):

    __gsignals__ = {
        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (GObject.SignalFlags.RUN_LAST,
                                        None,
                                        (GObject.TYPE_PYOBJECT,
                                         GObject.TYPE_PYOBJECT, 
                                         GObject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }

    _SORT_METHOD_INDEX = (SortMethods.BY_ALPHABET,
                          SortMethods.BY_TOP_RATED)
    _SORT_BY_ALPHABET = 0
    _SORT_BY_TOP_RATED = 1

    def __init__(self, db, cache, icons, show_ratings):
        Gtk.VBox.__init__(self)
        # app properties helper
        self.helper = AppPropertiesHelper(db, cache, icons)
        # misc internal containers
        self.header_hbox = Gtk.HBox()
        self.header_hbox.set_border_width(StockEms.XLARGE)
        self.pack_start(self.header_hbox, False, False, 0)
        self.tree_view_scroll = Gtk.ScrolledWindow()
        self.pack_start(self.tree_view_scroll, True, True, 0)

        # category label
        self.header_label = Gtk.Label()
        self.header_label.set_use_markup(True)
        self.header_hbox.pack_start(self.header_label, False, False, 0)

        # sort methods combobox
        self.sort_methods_combobox = self._get_sort_methods_combobox()
        alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)
        alignment.add(self.sort_methods_combobox)
        self.header_hbox.pack_end(alignment, False, False, 0)

        # content views
        self.tree_view = AppTreeView(self, icons,
                                     show_ratings, store=None)
        self.tree_view_scroll.add(self.tree_view)
        return

    def _get_sort_methods_combobox(self):
        combo = Gtk.ComboBoxText()
        combo.append_text(_("By Name"))
        combo.append_text(_("By Popularity"))
        combo.set_active(self._SORT_BY_TOP_RATED)
        return combo

    def set_header_labels(self, first_line, second_line):
        if second_line:
            markup = '%s\n<big><b>%s</b></big>' % (first_line, second_line)
        else:
            markup = "<big><b>%s</b></big>" % first_line
        return self.header_label.set_markup(markup)

    def set_model(self, model):
        self.tree_view.set_model(model)
        return

    def display_matches(self, matches):
        model = self.tree_view.get_model()
        model.set_from_matches(matches)
        return

    def clear_model(self):
        return self.tree_view.clear_model()

    def get_sort_mode(self):
        combo = self.sort_methods_combobox
        active_index = self.sort_methods_combobox.get_active()
        return self._SORT_METHOD_INDEX[active_index]
