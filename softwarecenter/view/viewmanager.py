# Copyright (C) 2010 Canonical
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

class ViewManager(object):

    def __init__(self, notebook_view):
        self.notebook_view = notebook_view
        self.all_views = {}
        self.view_to_pane = {}
    def register(self, view_widget, view_id):
        page_id = self.notebook_view.append_page(
            view_widget, gtk.Label(view_id)) # label is for debugging only
        self.all_views[view_id] = page_id
        self.view_to_pane[view_id] = view_widget

    def set_active_view(self, view_id):
        page_id = self.all_views[view_id]
        self.notebook_view.set_current_page(page_id)

    def get_active_view(self):
        page_id = self.notebook_view.get_current_page()
        for (k, v) in self.all_views.iteritems():
            if page_id == v:
                return k

    def get_notebook_page_from_view_id(self, view_page):
        return self.all_views[view_page]
    def get_view_widget(self, view_page):
        return self.view_to_pane[view_page]
