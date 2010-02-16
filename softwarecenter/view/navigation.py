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
    
    def __init__(self, software_pane):
        self.software_pane = software_pane
        # always start at main category view
        self._current_nav_item = NavigationItem(software_pane,
                                 NavigationItem.NAV_CATEGORY)
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

    #### just stubbed out for now ####
    # TODO:  Implement navigate_to() using one of:
    #        1. use the if switch as below and implement calls directly (yuck)
    #        2. pass the navigation function itself and associated arguments
    #           to the __init__ for each instance of a nav item
    #        3. NavigationItem is just an interface, add subclasses for each
    #           navigation impl

    # navigation types
    (NAV_CATEGORY,
     NAV_SUBCATEGORY,
     NAV_APPLIST,
     NAV_APPDETAILS,
     NAV_SEARCH) = range(5)

    def __init__(self, software_pane, nav_type):
        self.software_pane = software_pane
        self.nav_type = nav_type
        
    def navigate_to(self):
        if self.nav_type == self.NAV_CATEGORY:
            print "navigate_to NAV_CATEGORY"
        elif self.nav_type == self.NAV_SUBCATEGORY:
            print "navigate_to NAV_SUBCATEGORY"
        elif self.nav_type == self.NAV_APPLIST:
            print "navigate_to NAV_APPLIST"
        elif self.nav_type == self.NAV_APPDETAILS:
            print "navigate_to NAV_APPDETAILS"
        elif self.nav_type == self.NAV_SEARCH:
            print "navigate_to NAV_SEARCH"
        else:
            print "unrecognized nav_type"
