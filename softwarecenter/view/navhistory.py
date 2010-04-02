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
import copy
import logging

from softwarecenter.utils import unescape

# FIXME: sucks, move elsewhere
in_replay_history_mode = False

class NavigationHistory(object):
    """
    class to manage navigation history in the "Get Software" section (the
    available pane).
    """
    
    def __init__(self, available_pane):
        self.available_pane = available_pane
        # always start at main category view
        self._current_nav_item = CategoryViewNavigationItem(available_pane)
        # use stacks to track navigation history
        self._nav_back_stack = []
        self._nav_forward_stack = []
        
    def navigate(self, dest_nav_item):
        """
        append a new NavigationItem to the history stack
        """
        if in_replay_history_mode:
            return
        logging.debug("submit navitem for history: %s" % dest_nav_item)
        # TODO: Detect multiple clicks on the same nav button and filter
        #       them out - we don't want them in the history
        dest_nav_item.parent = self
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = dest_nav_item
        # reset navigation forward stack on a direct navigation
        self._nav_forward_stack = []
        # update buttons
        self.available_pane.back_forward.left.set_sensitive(True)
        self.available_pane.back_forward.right.set_sensitive(False)

    def nav_forward(self):
        """
        navigate forward one item in the history stack
        """
        self.available_pane.back_forward.left.set_sensitive(True)
        if len(self._nav_forward_stack) <= 1:
            self.available_pane.back_forward.right.set_sensitive(False)
        nav_item = self._nav_forward_stack.pop()
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        nav_item.navigate_to()
    
    def nav_back(self):
        """
        navigate back one item in the history stack
        """
        self.available_pane.back_forward.right.set_sensitive(True)
        if len(self._nav_back_stack) <= 1:
            self.available_pane.back_forward.left.set_sensitive(False)
        nav_item = self._nav_back_stack.pop()
        logging.debug("nav_back: %s" % nav_item)
        self._nav_forward_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        nav_item.navigate_to()
        
class NavigationItem(object):
    """
    class to implement navigation points to be managed in the history queues
    """

    def __init__(self, available_pane):
        self.available_pane = available_pane
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
        # first part is special and kept in remove_all
        self.available_pane.navigation_bar.remove_all(keep_first_part=True,
                                                      do_callback=False)

        for part in self.parts:
                self.available_pane.navigation_bar.add_with_id(unescape(part.label),
                                                               part.callback,
                                                               part.get_name(),
                                                               do_callback=False,
                                                               animate=False)
        if self.parts:
            self.parts[-1].do_callback()
        else:
            self.available_pane.navigation_bar.get_parts()[0].do_callback()

        in_replay_history_mode = False

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

class CategoryViewNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the main category view
    Note: all subclasses of NavigationItem are for debug use only and
          can be collapsed to the NavigationItem class if desired
    """
        
class AppListNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category
    Note: all subclasses of NavigationItem are for debug use only and
          can be collapsed to the NavigationItem class if desired
    """
            
class AppListSubcategoryNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category and subcategory
    Note: all subclasses of NavigationItem are for debug use only and
          can be collapsed to the NavigationItem class if desired
    """
        
class AppDetailsNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the details view for the
    specified application
    Note: all subclasses of NavigationItem are for debug use only and
          can be collapsed to the NavigationItem class if desired
    """
        
class SearchNavigationItem(NavigationItem):
    """
    navigation item that corresponds to a search in progress
    Note: all subclasses of NavigationItem are for debug use only and
          can be collapsed to the NavigationItem class if desired
    """
