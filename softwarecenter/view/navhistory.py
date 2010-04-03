# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

import gobject
import logging

from softwarecenter.utils import unescape

# FIXME: sucks, move elsewhere
in_replay_history_mode = False

class NavigationHistory(object):
    """
    class to manage navigation history in the "Get Software" section (the
    available pane).
    """

    MAX_NAV_ITEMS = 20  # limit number of NavItems allowed in the NavStack


    def __init__(self, available_pane):
        self.available_pane = available_pane
        # use stacks to track navigation history
        self._nav_stack = NavigationStack(self.MAX_NAV_ITEMS)

    def navigate(self, nav_item):
        """
        append a new NavigationItem to the history stack
        """
        if in_replay_history_mode:
            return

        nav_item.parent = self
        self._nav_stack.append(nav_item)

        if self._nav_stack.cursor > 0:
            self.available_pane.back_forward.left.set_sensitive(True)
        self.available_pane.back_forward.right.set_sensitive(False)

    def nav_forward(self):
        """
        navigate forward one item in the history stack
        """
        nav_item = self._nav_stack.step_forward()
        nav_item.navigate_to()

        if self._nav_stack.at_end():
            self.available_pane.back_forward.right.set_sensitive(False)
        self.available_pane.back_forward.left.set_sensitive(True)

    def nav_back(self):
        """
        navigate back one item in the history stack
        """
        nav_item = self._nav_stack.step_back()
        nav_item.navigate_to()

        if self._nav_stack.at_start():
            self.available_pane.back_forward.left.set_sensitive(False)
        self.available_pane.back_forward.right.set_sensitive(True)


class NavigationItem(object):
    """
    class to implement navigation points to be managed in the history queues
    """

    def __init__(self, available_pane, update_available_pane_cb):
        self.available_pane = available_pane
        self.update_available_pane = update_available_pane_cb
        self.apps_category = available_pane.apps_category
        self.apps_subcategory = available_pane.apps_subcategory
        self.apps_search_term = available_pane.apps_search_term
        self.current_app = available_pane.get_current_app()
        self.parts = self.available_pane.navigation_bar.get_parts()

    def navigate_to(self):
        """
        navigate to the view that corresponds to this NavigationItem
        """
        global in_replay_history_mode
        in_replay_history_mode = True
        self.available_pane.apps_category = self.apps_category
        self.available_pane.apps_subcategory = self.apps_subcategory
        self.available_pane.apps_search_term = self.apps_search_term
        self.available_pane.searchentry.set_text(self.apps_search_term)
        self.available_pane.searchentry.set_position(-1)
        self.available_pane.app_details.show_app(self.current_app)

        nav_bar = self.available_pane.navigation_bar
        nav_bar.remove_all(do_callback=False)

        for part in self.parts[1:]:
            nav_bar.add_with_id(unescape(part.label),
                                part.callback,
                                part.get_name(),
                                do_callback=False,
                                animate=False)

        gobject.idle_add(self._update_available_pane_cb, nav_bar)
        in_replay_history_mode = False

    def _update_available_pane_cb(self, nav_bar):
        last_part = nav_bar.get_parts()[-1]
        nav_bar.set_active_no_callback(last_part)
        self.update_available_pane()
        return False

    def __str__(self):
        details = []
        details.append("\n%s" % type(self))
        category_name = ""
        if self.apps_category:
            category_name = self.apps_category.name
        details.append("  apps_category.name: %s" % category_name)
        subcategory_name = ""
        if self.apps_subcategory:
            subcategory_name = self.apps_subcategory.name
        details.append("  apps_subcategory.name: %s" % subcategory_name)
        details.append("  current_app: %s" % self.current_app)
        details.append("  apps_search_term: %s" % self.apps_search_term)
        return '\n'.join(details)


class NavigationStack(object):

    def __init__(self, max_length):
        self.max_length = max_length
        self.stack = []
        self.cursor = 0
        return

    def __len__(self):
        return len(self.stack)

    def __repr__(self):
        BOLD = "\033[1m"
        RESET = "\033[0;0m"
        s = '['
        for i, item in enumerate(self.stack):
            if i != self.cursor:
                s += str(item.parts[-1].label) + ', '
            else:
                s += BOLD + str(item.parts[-1].label) + RESET + ', '
        return s + ']'

    def _isok(self, item):
        if len(self.stack) == 0: return True
        pre_item = self.stack[-1]
        if pre_item.parts[-1].label == item.parts[-1].label:
            if pre_item.apps_search_term != item.apps_search_term:
                return True
            return False
        return True

    def append(self, item):
        if not self._isok(item):
            self.cursor = len(self.stack)-1
            print 'A:', repr(self)
            return
        if len(self.stack) + 1 > self.max_length:
            self.stack.pop(0)
        self.stack.append(item)
        self.cursor = len(self.stack)-1
        print 'A:', repr(self)
        return

    def step_back(self):
        self.cursor -= 1
        print 'B:', repr(self)
        return self.stack[self.cursor]

    def step_forward(self):
        self.cursor += 1
        print 'B:', repr(self)
        return self.stack[self.cursor]

    def at_end(self):
        return self.cursor == len(self.stack)-1

    def at_start(self):
        return self.cursor == 0
