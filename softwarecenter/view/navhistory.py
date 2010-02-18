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
        
    def navigate(self, dest_nav_item):
        """
        append a new NavigationItem to the history stack
        """
        # we never want to append a second navigation item of the same
        # type as this is not useful for history and would only occur
        # under the following conditions:  1. when there are multiple clicks
        # on the same navigation button, or 2. when additional calls
        # to the navigate method occur due to GTK events that get
        # generated as side effects when switching views and setting up
        # navigation buttons (and these should be ignored)
        if type(dest_nav_item) == type(self._current_nav_item):
            return
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
        self._nav_forward_stack.append(self._current_nav_item)
        self._current_nav_item = nav_item
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
        
class CategoryViewNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the main category view
    """
    def __init__(self, available_pane):
        self.available_pane = available_pane
        
    def navigate_to(self):
        self.available_pane.on_navigation_category(None, None)
        
class AppListNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
        print "create AppListNavigationItem"
#        print "...with apps_category.name: %s" % apps_category or apps_category.name
#        print "...with apps_subcategory.name: %s" % apps_subcategory or apps_subcategory.name
        print "...with apps_search_term: %s" % apps_search_term
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        
    def navigate_to(self):
        print "AppListNavigationItem.navigate_to() "
        self.available_pane.apps_category = self.apps_category
        self.available_pane.set_category(self.apps_category)
        self.available_pane.apps_subcategory = self.apps_subcategory
        self.available_pane.apps_search_term = self.apps_search_term
        self.available_pane.on_navigation_list(None, None)
            
class AppListSubcategoryNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category and subcategory
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
        print "create AppListSubcategoryNavigationItem"
#        print "...with apps_category.name: %s" % apps_category or apps_category.name
#        print "...with apps_subcategory.name: %s" % apps_subcategory or apps_subcategory.name
        print "...with apps_search_term: %s" % apps_search_term
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        
    def navigate_to(self):
        print "AppListNavigationItem.navigate_to() "
        self.available_pane.apps_category = self.apps_category
        self.available_pane.apps_subcategory = self.apps_subcategory
        self.available_pane.apps_search_term = self.apps_search_term
        self.available_pane.set_category(self.apps_subcategory)
        # check state of navigation bar and make sure we build up all
        # buttons as needed
        self.available_pane.navigation_bar.add_with_id(
            self.apps_subcategory.name, self.available_pane.on_navigation_list_subcategory, "subcat")
        self.available_pane.on_navigation_list_subcategory(None, None)
        
class AppDetailsNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the details view for the
    specified application
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       current_app):
#        print "create AppDetailsNavigationItem"
#        print "...with apps_category.name: %s" % apps_category or apps_category.name
#        print "...with apps_subcategory.name: %s" % apps_subcategory or apps_subcategory.name
#        print "...with current_app: %s" % current_app
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.current_app = current_app
        
    def navigate_to(self):
        print "AppDetailsNavigationItem.navigate_to() "
        if self.available_pane.apps_subcategory:
            self.available_pane.current_app_by_subcategory[self.available_pane.apps_subcategory] = self.current_app
        else:
            self.available_pane.current_app_by_category[self.available_pane.apps_category] = self.current_app
        self.available_pane.set_category(self.apps_subcategory or self.apps_category)
        # check state of navigation bar and make sure we build up all
        # buttons as needed
        if not self.available_pane.navigation_bar.get_button_from_id("list"):
            self.available_pane.navigation_bar.add_with_id(self.apps_category.name,
                                                           self.available_pane.on_navigation_details,
                                                           "list")
        if self.apps_subcategory and not self.available_pane.navigation_bar.get_button_from_id("subcat"):
            self.available_pane.navigation_bar.add_with_id(self.apps_subcategory.name,
                                                           self.available_pane.on_navigation_details,
                                                           "subcat")
        self.available_pane.navigation_bar.add_with_id(self.current_app.name,
                                                       self.available_pane.on_navigation_details,
                                                       "details")
        self.available_pane.app_details.show_app(self.current_app)
        self.available_pane.on_navigation_details(None, None)
        
class SearchNavigationItem(NavigationItem):
    """
    navigation item that corresponds to a search in progress
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
        print "create SearchNavigationItem"
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        print "create AppListSubcategoryNavigationItem"
#        print "...with apps_category.name: %s" % apps_category or apps_category.name
#        print "...with apps_subcategory.name: %s" % apps_subcategory or apps_subcategory.name
        print "...with apps_search_term: %s" % apps_search_term
        
    def navigate_to(self):
        print "SearchNavigationItem.navigate_to() "
        
