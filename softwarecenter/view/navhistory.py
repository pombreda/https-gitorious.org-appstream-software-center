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
        # flag to skip adding a NavigationItem to history
        self._skip_history = False
        
    def navigate(self, dest_nav_item):
        """
        append a new NavigationItem to the history stacks
        """
        print "navigate"
        if self._skip_history:
            return
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = dest_nav_item
        self.available_pane.back_forward.left.set_sensitive(True)
        # reset navigation forward stack on a direct navigation
        self._nav_forward_stack = []
        self.available_pane.back_forward.right.set_sensitive(False)
        
    def nav_forward(self):
        """
        navigate forward one item in the history stack
        """
        print "nav_forward"
        if len(self._nav_forward_stack) <= 1:
            self.available_pane.back_forward.right.set_sensitive(False)
        nav_item = self._nav_forward_stack.pop()
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        self.available_pane.back_forward.left.set_sensitive(True)
        self._skip_history = True
        nav_item.navigate_to()
        self._skip_history = False
    
    def nav_back(self):
        """
        navigate back one item in the history stack
        """
        print "nav_back"
        if len(self._nav_back_stack) <= 1:
            self.available_pane.back_forward.left.set_sensitive(False)
        nav_item = self._nav_back_stack.pop()
        self._nav_forward_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        self.available_pane.back_forward.right.set_sensitive(True)
        self._skip_history = True
        nav_item.navigate_to()
        self._skip_history = False
        
class NavigationItem(object):
    """
    interface class to represent navigation points for use with the
    NavigationHistory class
    """
    
    def navigate_to(self):
        """
        stub implementation - navigate to the view that corresponds
        to this NavigationItem
        """
        pass
        
class CategoryViewNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane):
        print "create CategoryViewNavigationItem"
        self.available_pane = available_pane
        
    def navigate_to(self):
        print "CategoryViewNavigationItem.navigate_to() "
        self.available_pane.on_navigation_category(None, None)
        
class CategoryActivatedNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane, category):
        print "create CategoryActivatedNavigationItem with category.name: %s" % category.name
        self.available_pane = available_pane
        self.category = category
        
    def navigate_to(self):
        print "CategoryActivatedNavigationItem.navigate_to() "
        self.available_pane.on_category_activated(None, self.category)
        
class SubcategoryActivatedNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane, category):
        print "create SubcategoryActivatedNavigationItem with category.name: %s" % category.name
        self.available_pane = available_pane
        self.category = category
        
    def navigate_to(self):
        print "SubcategoryActivatedNavigationItem.navigate_to() "
        self.available_pane.on_subcategory_activated(None, self.category)
        
class AppListNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane):
        print "create AppListNavigationItem"
        self.available_pane = available_pane
        
    def navigate_to(self):
        print "AppListNavigationItem.navigate_to() "
        
class AppDetailsNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane):
        print "create AppDetailsNavigationItem"
        self.available_pane = available_pane
        
    def navigate_to(self):
        print "AppDetailsNavigationItem.navigate_to() "
        
class SearchNavigationItem(NavigationItem):
    """
    """
    def __init__(self, available_pane):
        print "create SearchNavigationItem"
        self.available_pane = available_pane
        
    def navigate_to(self):
        print "SearchNavigationItem.navigate_to() "
        
