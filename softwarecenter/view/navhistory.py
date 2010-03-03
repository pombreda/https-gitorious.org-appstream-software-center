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

# FIXME: sucks, move elsewhere
in_replay_history_mode = False

class NavigationHistory(object):
    """
    Class to manage navigation history in the "Get Software" section (the
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
    interface class to represent navigation points for use with the
    NavigationHistory class
    """

    def __init__(self, available_pane):
        self.available_pane = available_pane
        self.apps_category = available_pane.apps_category
        self.apps_subcategory = available_pane.apps_subcategory
        self.apps_search_term = available_pane.apps_search_term
        self.current_app = available_pane.get_current_app()
        self.parts = self.available_pane.navigation_bar.get_parts()[:]
    
    def navigate_to(self):
        """
        stub implementation - navigate to the view that corresponds
        to this NavigationItem
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
        self.available_pane.navigation_bar.remove_all()
        for part in self.parts[1:]:
            self.available_pane.navigation_bar.add_with_id(part.label, part.callback, part.id, do_callback=False, animate=False)
        self.parts[-1].activate()
        in_replay_history_mode = False
        
class CategoryViewNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the main category view
    """

    def __str__(self):
        return "* CategoryViewNavigationItem"
        
class AppListNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category
    """
        
    def __str__(self):
        details = []
        details.append("* AppListNavigationItem")
        details.append("\n")
        details.append("  apps_category.name: %s" % self.apps_category.name)
        details.append("\n")
        if (self.apps_subcategory):
            details.append("  apps_subcategory.name: %s" % self.apps_category.name)
        else:
            details.append("  apps_subcategory.name: none")
        details.append("\n")
        details.append("  apps_search_term: %s" % self.apps_search_term)
        return ''.join(details)
            
class AppListSubcategoryNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category and subcategory
    """
        
    def __str__(self):
        details = []
        details.append("* AppListSubcategoryNavigationItem")
        details.append("\n")
        details.append("  apps_category.name: %s" % self.apps_category.name)
        details.append("\n")
        if (self.apps_subcategory):
            details.append("  apps_subcategory.name: %s" % self.apps_subcategory.name)
        else:
            details.append("  apps_subcategory.name: none")
        details.append("\n")
        details.append("  apps_search_term: %s" % self.apps_search_term)
        return ''.join(details)
        
class AppDetailsNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the details view for the
    specified application
    """
    def __str__(self):
        details = []
        details.append("* AppDetailsNavigationItem")
        details.append("\n")
        details.append("  apps_category.name: %s" % self.apps_category.name)
        details.append("\n")
        if (self.apps_subcategory):
            details.append("  apps_subcategory.name: %s" % self.apps_category.name)
        else:
            details.append("  apps_subcategory.name: none")
        details.append("\n")
        details.append("  current_app: %s" % self.current_app)
        return ''.join(details)
        
# TODO: remove this class if not needed
class SearchNavigationItem(NavigationItem):
    """
    navigation item that corresponds to a search in progress
    """
