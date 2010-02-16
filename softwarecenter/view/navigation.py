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
    Class to manage navigation history in the software pane.
    """
    
    def __init__(self, software_pane):
        self.software_pane = software_pane
        # always start at main category view
        self._current_nav_item = CategoryNavigationItem(software_pane)
        # use stacks to track navigation history
        self._nav_back_stack = []
        self._nav_forward_stack = []
        
    def navigate(self, dest_nav_item):
        """
        append a new NavigationItem to the history stacks
        """
        print "navigate"
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = dest_nav_item
        self.software_pane.back_forward.left.set_sensitive(True)
        # reset navigation stacks on a direct navigation
        self._nav_forward_stack = []
        self.software_pane.back_forward.right.set_sensitive(False)
        
    def nav_forward(self):
        """
        navigate forward one item in the history stack
        """
        print "nav_forward"
        if len(self._nav_forward_stack) <= 1:
            self.software_pane.back_forward.right.set_sensitive(False)
        nav_item = self._nav_forward_stack.pop()
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        self.software_pane.back_forward.left.set_sensitive(True)
        nav_item.navigate_to()
    
    def nav_back(self):
        """
        navigate back one item in the history stack
        """
        print "nav_back"
        if len(self._nav_back_stack) <= 1:
            self.software_pane.back_forward.left.set_sensitive(False)
        nav_item = self._nav_back_stack.pop()
        self._nav_forward_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
        self.software_pane.back_forward.right.set_sensitive(True)
        nav_item.navigate_to()
        
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
        
class CategoryNavigationItem(NavigationItem):
    """
    """
    def __init__(self, software_pane):
        self.software_pane = software_pane
        
    def navigate_to(self):
        print "CategoryNavigationItem.navigate_to() "
        
class SubcategoryNavigationItem(NavigationItem):
    """
    """
    def __init__(self, software_pane):
        self.software_pane = software_pane
        
    def navigate_to(self):
        print "SubcategoryNavigationItem.navigate_to() "
        
class AppListNavigationItem(NavigationItem):
    """
    """
    def __init__(self, software_pane):
        self.software_pane = software_pane
        
    def navigate_to(self):
        print "AppListNavigationItem.navigate_to() "
        
class AppDetailsNavigationItem(NavigationItem):
    """
    """
    def __init__(self, software_pane):
        self.software_pane = software_pane
        
    def navigate_to(self):
        print "AppDetailsNavigationItem.navigate_to() "
        
class SearchNavigationItem(NavigationItem):
    """
    """
    def __init__(self, software_pane):
        self.software_pane = software_pane
        
    def navigate_to(self):
        print "SearchNavigationItem.navigate_to() "
        
