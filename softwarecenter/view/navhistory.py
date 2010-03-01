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
        print ">>> submitting navitem for history: "
        print dest_nav_item
        # TODO: Detect multiple clicks on the same nav button and filter
        #       them out of the history
        self._nav_back_stack.append(self._current_nav_item)
        self._current_nav_item = dest_nav_item
        # reset navigation forward stack on a direct navigation
        self._nav_forward_stack = []
        # update buttons
        self.available_pane.back_forward.left.set_sensitive(True)
        self.available_pane.back_forward.right.set_sensitive(False)
        self.print_nav_state("nav state after submit")
        
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
        self.print_nav_state("after nav forward")
    
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
        self.print_nav_state("after nav back")
        
    def print_nav_state(self, desc_string):
        print "### %s ###" % desc_string
        print "CURRENT:"
        print self._current_nav_item
        print "BACK:"
        for item in self._nav_back_stack:
            print item
        print "FORWARD:"
        for item in self._nav_forward_stack:
            print item
        
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
        self.available_pane.on_navigation_category(None, None, skip_history=True)
        
    def __str__(self):
        return "* CategoryViewNavigationItem"
        
class AppListNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the application list for the
    specified category
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
#        print "create AppListNavigationItem"
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        
    def navigate_to(self):
        print "AppListNavigationItem.navigate_to() "
        self.available_pane.apps_category = self.apps_category
        self.available_pane.apps_subcategory = self.apps_subcategory
        self.available_pane.apps_search_term = self.apps_search_term
        self.available_pane.set_category(self.apps_category, do_callback=False)
        self.available_pane.on_navigation_list(None, None, skip_history=True)
        
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
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
#        print "create AppListSubcategoryNavigationItem"
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        
    def navigate_to(self):
        print "AppListSubcategoryNavigationItem.navigate_to() "
        self.available_pane.apps_category = self.apps_category
        self.available_pane.apps_subcategory = self.apps_subcategory
        self.available_pane.apps_search_term = self.apps_search_term
        self.available_pane.set_category(self.apps_subcategory, do_callback=False)
        # check state of navigation bar and make sure we build up all
        # buttons as needed
        self.available_pane.navigation_bar.add_with_id(
            self.apps_subcategory.name,
            self.available_pane.on_navigation_list_subcategory,
            self.available_pane.NAV_BUTTON_ID_SUBCAT,
            do_callback=False)
        self.available_pane.on_navigation_list_subcategory(None, None, skip_history=True)
        
    def __str__(self):
        details = []
        details.append("* AppListSubcategoryNavigationItem")
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
        
class AppDetailsNavigationItem(NavigationItem):
    """
    navigation item that corresponds to the details view for the
    specified application
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       current_app):
#        print "create AppDetailsNavigationItem"
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.current_app = current_app
        
    def navigate_to(self):
        print "AppDetailsNavigationItem.navigate_to() "
        self.available_pane.apps_category = self.apps_category
        self.available_pane.apps_subcategory = self.apps_subcategory
        if self.available_pane.apps_subcategory:
            self.available_pane.current_app_by_subcategory[self.available_pane.apps_subcategory] = self.current_app
        else:
            self.available_pane.current_app_by_category[self.available_pane.apps_category] = self.current_app
        self.available_pane.set_category(self.apps_subcategory or self.apps_category, do_callback=False)
        # check state of navigation bar and make sure we build up all
        # buttons as needed
        if not self.available_pane.navigation_bar.get_button_from_id(self.available_pane.NAV_BUTTON_ID_LIST):
            self.available_pane.navigation_bar.add_with_id(self.apps_category.name,
                                                           self.available_pane.on_navigation_list,
                                                           self.available_pane.NAV_BUTTON_ID_LIST,
                                                           do_callback=False)
        if (self.apps_subcategory and 
            not self.available_pane.navigation_bar.get_button_from_id(self.available_pane.NAV_BUTTON_ID_SUBCAT)):
            self.available_pane.navigation_bar.add_with_id(self.apps_subcategory.name,
                                                           self.available_pane.on_navigation_details_subcategory,
                                                           self.available_pane.NAV_BUTTON_ID_SUBCAT,
                                                           do_callback=False)
        self.available_pane.navigation_bar.add_with_id(self.current_app.name,
                                                       self.available_pane.on_navigation_details,
                                                       self.available_pane.NAV_BUTTON_ID_DETAILS,
                                                       do_callback=False)
        self.available_pane.app_details.show_app(self.current_app)
        self.available_pane.on_navigation_details(None, None, skip_history=True)
        
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
#        details.append("\n")
#        details.append("  apps_search_term: %s" % self.apps_search_term)
        details.append("\n")
        details.append("  current_app: %s" % self.current_app)
        return ''.join(details)
        
class SearchNavigationItem(NavigationItem):
    """
    navigation item that corresponds to a search in progress
    """
    def __init__(self, available_pane, apps_category,
                                       apps_subcategory,
                                       apps_search_term):
#        print "create SearchNavigationItem"
        self.available_pane = available_pane
        self.apps_category = apps_category
        self.apps_subcategory = apps_subcategory
        self.apps_search_term = apps_search_term
        
    def navigate_to(self):
        print "SearchNavigationItem.navigate_to() "

