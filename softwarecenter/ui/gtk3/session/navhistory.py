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

from gi.repository import GObject
import logging

from softwarecenter.utils import unescape

# FIXME: sucks, move elsewhere
in_replay_history_mode = False



class NavigationHistory(object):
    """
    class to manage navigation history in the "Get Software" section (the
    available pane).
    """
    MAX_NAV_ITEMS = 25  # limit number of NavItems allowed in the NavStack

    def __init__(self, back_forward):
        self.stack = NavigationStack(self.MAX_NAV_ITEMS)
        self.back_forward = back_forward
        return

    def get_current(self, pane):
        return self.stack[stack.cursor]

    def append(self, nav_item):
        """
        append a new NavigationItem to the history stack
        """
        if in_replay_history_mode:
            return

        stack = self.stack
        # reset navigation forward stack items on a direct navigation
        #~ stack.clear_forward_items()
        stack.append(nav_item)

        if stack.cursor > 1:
            self._nav_back_set_sensitive(True)
        self._nav_forward_set_sensitive(False)

    def nav_forward(self, pane):
        """
        navigate forward one item in the history stack
        """
        stack = self.stack
        nav_item = stack.step_forward()
        nav_item.navigate_to()

        self._nav_back_set_sensitive(True)
        if stack.at_end():
            if self.back_forward.right.has_focus():
                self.back_forward.left.grab_focus()
            self._nav_forward_set_sensitive(False)

    def nav_back(self, pane):
        """
        navigate back one item in the history stack
        """

        stack = self.stack
        nav_item = stack.step_back()
        nav_item.navigate_to()

        self._nav_forward_set_sensitive(True)
        if stack.at_start():
            if self.back_forward.left.has_focus():
                self.back_forward.right.grab_focus()
            self._nav_back_set_sensitive(False)

    def reset(self):
        """
        reset the navigation history by clearing the history stack and
        setting the navigation UI items insensitive
        """
        self.stack.reset()
        self._nav_back_set_sensitive(False)
        self._nav_forward_set_sensitive(False)
        
    def _nav_back_set_sensitive(self, is_sensitive):
        self.back_forward.left.set_sensitive(is_sensitive)
        #~ self.navhistory_back_action.set_sensitive(is_sensitive)

    def _nav_forward_set_sensitive(self, is_sensitive):
        self.back_forward.right.set_sensitive(is_sensitive)
        #~ self.navhistory_forward_action.set_sensitive(is_sensitive)


class NavigationItem(object):
    """
    class to implement navigation points to be managed in the history queues
    """

    def __init__(self, view_manager, pane, page, view_state, callback):
        self.view_manager = view_manager
        self.pane = pane
        self.page = page
        self.view_state = view_state
        self.callback = callback
        return

    def __str__(self):
        facet = self.pane.pane_name.replace(' ', '')[:6]
        return "%s:%s %s" % (facet, self.page, str(self.view_state))

    def navigate_to(self):
        """
        navigate to the view that corresponds to this NavigationItem
        """
        global in_replay_history_mode
        in_replay_history_mode = True

        self.view_manager.display_page(self.pane, self.page,
                       self.view_state, self.callback)

        in_replay_history_mode = False


class NavigationStack(object):
    """
    a navigation history stack
    """

    def __init__(self, max_length):
        self.max_length = max_length
        self.stack = []
        self.cursor = 0

    def __len__(self):
        return len(self.stack)

    def __repr__(self):
        BOLD = "\033[1m"
        RESET = "\033[0;0m"
        s = '['
        for i, item in enumerate(self.stack):
            if i != self.cursor:
                s += str(item) + ', '
            else:
                s += BOLD + str(item) + RESET + ', '
        return s + ']'

    def __getitem__(self, item):
        return self.stack[item]

    def _isok(self, item):
        if item.page is not None and item.page < 0:
            print 'not ok cos page is foobar'
            return False
        if len(self) == 0:
            return True
        last = self[-1]
        if str(item) == str(last):
            print 'not ok cos str is foobar',  str(item), str(last)
            return False
        return True

    def append(self, item):
        print item, self._isok(item)
        if not self._isok(item):
            self.cursor = len(self.stack)-1
            #~ logging.debug('A:%s' % repr(self))
            print 'A:%s' % repr(self)
            return
        if len(self.stack) + 1 > self.max_length:
            self.stack.pop(1)
        self.stack.append(item)
        self.cursor = len(self.stack)-1
        #~ logging.debug('A:%s' % repr(self))
        print 'A:%s' % repr(self)
        return

    def step_back(self):
        if self.cursor > 0:
            self.cursor -= 1
        else:
            self.cursor = 0
        logging.debug('B:%s' % repr(self))
        return self.stack[self.cursor]

    def step_forward(self):
        if self.cursor < len(self.stack)-1:
            self.cursor += 1
        else:
            self.cursor = len(self.stack)-1
        logging.debug('B:%s' % repr(self))
        return self.stack[self.cursor]

    def clear_forward_items(self):
        self.stack = self.stack[:(self.cursor + 1)]

    def at_end(self):
        return self.cursor == len(self.stack)-1

    def at_start(self):
        return self.cursor == 0

    def reset(self):
        self.stack = []
        self.cursor = 0
