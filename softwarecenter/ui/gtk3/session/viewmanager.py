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

from gi.repository import Gtk

from navhistory import NavigationHistory, NavigationItem
from softwarecenter.ui.gtk3.widgets.backforward import BackForwardButton
from softwarecenter.ui.gtk3.widgets.searchentry import SearchEntry

_viewmanager = None # the gobal Viewmanager instance


def get_viewmanager():
    return _viewmanager


class ViewManager(object):

    def __init__(self, notebook_view):
        self.notebook_view = notebook_view
        self.search_entry = SearchEntry()
        self.search_entry.connect(
            "terms-changed", self.on_search_terms_changed)

        self.back_forward = BackForwardButton()
        self.back_forward.connect(
            "left-clicked", self.on_nav_back_clicked)
        self.back_forward.connect(
            "right-clicked", self.on_nav_forward_clicked)

        self.navhistory = NavigationHistory(self.back_forward)

        self.all_views = {}
        self.view_to_pane = {}
        self._globalise_instance()

    def _globalise_instance(self):
        global _viewmanager
        if _viewmanager is not None:
            msg = "Only one instance of ViewManager is allowed!"
            raise SystemExit, msg
        else:
            _viewmanager = self

    def on_search_terms_changed(self, widget, new_text):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_search_terms_changed"):
            pane.on_search_terms_changed(widget, new_text)
        return

    def on_nav_back_clicked(self, widget):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_nav_back_clicked"):
            pane.on_nav_back_clicked(widget)
        return

    def on_nav_forward_clicked(self, widget):
        pane = self.get_current_view_widget()
        if hasattr(pane, "on_nav_forward_clicked"):
            pane.on_nav_forward_clicked(widget)
        return

    def register(self, pane, view_id):
        page_id = self.notebook_view.append_page(
            pane, Gtk.Label.new("View %s" % view_id)) # label is for debugging only
        self.all_views[view_id] = page_id
        self.view_to_pane[view_id] = pane

    def get_current_view_widget(self):
        current_view = self.get_active_view()
        return self.get_view_widget(current_view)

    def get_view_id_from_page_id(self, page_id):
        for (k, v) in self.all_views.iteritems():
            if page_id == v:
                return k

    def set_active_view(self, view_id):
        page_id = self.all_views[view_id]
        view_widget = self.get_view_widget(view_id)
    
        view_page = view_widget.get_current_page()
        view_state = view_widget.state
        callback = view_widget.get_callback_for_page(view_page,
                                                     view_state)

        nav_item = NavigationItem(self, view_widget, view_page,
                                  view_state.copy(), callback)
        self.navhistory.append(nav_item)

        self.notebook_view.set_current_page(page_id)
        if view_widget:
            view_widget.init_view()

    def get_active_view(self):
        page_id = self.notebook_view.get_current_page()
        return self.get_view_id_from_page_id(page_id)

    def get_notebook_page_from_view_id(self, view_id):
        return self.all_views[view_id]
        
    def get_view_widget(self, view_id):
        return self.view_to_pane[view_id]

    def get_latest_nav_item(self):
        return self.navhistory.stack[-1]

    def display_page(self, pane, page, view_state, callback):
        nav_item = NavigationItem(self, pane, page,
                                  view_state.copy(), callback)

        self.navhistory.append(nav_item)
        pane.state = view_state

        text = view_state.search_term
        if text != self.search_entry.get_text():
            self.search_entry.set_text_with_no_signal(text)

        if callback is not None:
            callback(page, view_state)

        if page is not None:
            pane.notebook.set_current_page(page)
    
        if self.get_current_view_widget() != pane:
            view_id = None
            for view_id, widget in self.view_to_pane.iteritems():
                if widget == pane: break
    
            self.set_active_view(view_id)
        return

    def nav_back(self, pane):
        self.navhistory.nav_back(pane)

    def nav_forward(self, pane):
        self.navhistory.nav_forward(pane)

    def get_global_searchentry(self):
        return self.search_entry

    def get_global_backforward(self):
        return self.back_forward
