# Copyright (C) 2009 Canonical
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

import apt
import gettext
import gobject
import glib
import gtk
import logging
import os
import sys
import xapian

import dialogs

from gettext import gettext as _

from softwarecenter.enums import (
    ACTION_BUTTON_ID_INSTALL,
    DEFAULT_SEARCH_LIMIT,
    NAV_BUTTON_ID_LIST,
    NAV_BUTTON_ID_DETAILS,
    NAV_BUTTON_ID_PURCHASE,
    NAV_BUTTON_ID_SUBCAT,
    NAV_BUTTON_ID_CATEGORY,
    NAV_BUTTON_ID_SEARCH,
    NAV_BUTTON_ID_PREV_PURCHASES,
    )
from softwarecenter.paths import APP_INSTALL_PATH, ICON_PATH, XAPIAN_BASE_PATH
from softwarecenter.utils import wait_for_apt_cache_ready

from softwarecenter.distro import get_distro

from appview import AppStore, AppViewFilter
#from catview_webkit import CategoriesViewWebkit as CategoriesView
from catview_gtk import LobbyViewGtk, SubCategoryViewGtk
from catview import Category, CategoriesView

from softwarepane import SoftwarePane

from widgets.backforward import BackForwardButton

from navhistory import NavigationHistory, NavigationItem

LOG = logging.getLogger(__name__)

class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    # notebook pages
    (PAGE_CATEGORY,
     PAGE_SUBCATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS,
     PAGE_APP_PURCHASE) = range(5)
     
    __gsignals__ = {'available-pane-created':(gobject.SIGNAL_RUN_FIRST,
                                              gobject.TYPE_NONE,
                                              ())}

    def __init__(self, 
                 cache,
                 db, 
                 distro, 
                 icons, 
                 datadir, 
                 navhistory_back_action, 
                 navhistory_forward_action):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir)
        self.searchentry.set_sensitive(False)
        # navigation history actions
        self.navhistory_back_action = navhistory_back_action
        self.navhistory_forward_action = navhistory_forward_action
        # state
        self.apps_category = None
        self.apps_subcategory = None
        self.previous_purchases_query = None
        self.apps_search_term = ""
        self.apps_limit = 0
        self.apps_filter = AppViewFilter(db, cache)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self._status_text = ""
        self.current_app_by_category = {}
        self.current_app_by_subcategory = {}
        self.pane_name = _("Get Software")
        # add nav history back/forward buttons
        if self.navhistory_back_action:
            self.navhistory_back_action.set_sensitive(False)
        if self.navhistory_forward_action:
            self.navhistory_forward_action.set_sensitive(False)
        # note:  this is hacky, would be much nicer to make the custom self/right
        # buttons in BackForwardButton to be gtk.Activatable/gtk.Widgets, then wire in the
        # actions using e.g. self.navhistory_back_action.connect_proxy(self.back_forward.left),
        # but couldn't seem to get this to work..so just wire things up directly
        self.back_forward = BackForwardButton()
        self.back_forward.connect("left-clicked", self.on_nav_back_clicked)
        self.back_forward.connect("right-clicked", self.on_nav_forward_clicked)
        self.top_hbox.pack_start(self.back_forward, expand=False)
        # nav buttons first in the panel
        self.top_hbox.reorder_child(self.back_forward, 0)
        if self.navhistory_back_action and self.navhistory_forward_action:
            self.nav_history = NavigationHistory(self,
                                                 self.back_forward,
                                                 self.navhistory_back_action,
                                                 self.navhistory_forward_action)

    def init_view(self):
        if not self.view_initialized:
            self.spinner_view.set_text(_('Loading Categories'))
            self.spinner_view.start()
            self.spinner_view.show()
            self.spinner_notebook.set_current_page(self.PAGE_SPINNER)
            self.window.set_cursor(self.busy_cursor)
            
            while gtk.events_pending():
                gtk.main_iteration()

            # open the cache since we are initializing the UI for the first time    
            glib.idle_add(self.cache.open)
            
            SoftwarePane.init_view(self)
            # categories, appview and details into the notebook in the bottom
            self.scroll_categories = gtk.ScrolledWindow()
            self.scroll_categories.set_policy(gtk.POLICY_AUTOMATIC, 
                                            gtk.POLICY_AUTOMATIC)
            self.cat_view = LobbyViewGtk(self.datadir, APP_INSTALL_PATH,
                                           self.cache,
                                           self.db,
                                           self.icons,
                                           self.apps_filter)
            self.scroll_categories.add(self.cat_view)
            self.notebook.append_page(self.scroll_categories, gtk.Label("categories"))

            # sub-categories view
            self.subcategories_view = SubCategoryViewGtk(self.datadir,
                                                     APP_INSTALL_PATH,
                                                     self.cache,
                                                     self.db,
                                                     self.icons,
                                                     self.apps_filter,
                                                     root_category=self.cat_view.categories[0])
            self.subcategories_view.connect(
                "category-selected", self.on_subcategory_activated)
            self.subcategories_view.connect(
                "show-category-applist", self.on_show_category_applist)
            self.scroll_subcategories = gtk.ScrolledWindow()
            self.scroll_subcategories.set_policy(
                gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            self.scroll_subcategories.add(self.subcategories_view)
            self.notebook.append_page(self.scroll_subcategories,
                                        gtk.Label(NAV_BUTTON_ID_SUBCAT))

            # app list
            self.notebook.append_page(self.box_app_list,
                                        gtk.Label(NAV_BUTTON_ID_LIST))

            self.cat_view.connect("category-selected", self.on_category_activated)
            self.cat_view.connect("application-selected", self.on_application_selected)
            self.cat_view.connect("application-activated", self.on_application_activated)

            # details
            self.notebook.append_page(self.scroll_details, gtk.Label(NAV_BUTTON_ID_DETAILS))

            # purchase view
            self.notebook.append_page(self.purchase_view, gtk.Label(NAV_BUTTON_ID_PURCHASE))
        
            # set status text
            self._update_status_text(len(self.db))

            # home button
            self.navigation_bar.add_with_id(self.pane_name,
                                            self.on_navigation_category,
                                            NAV_BUTTON_ID_CATEGORY,
                                            do_callback=True,
                                            animate=False)
                                            
            # install backend
            self.backend.connect("transactions-changed", self._on_transactions_changed)
            # now we are initialized
            self.searchentry.set_sensitive(True)
            self.emit("available-pane-created")
            self.show_all()
            self.spinner_view.stop()
            self.spinner_notebook.set_current_page(self.PAGE_APPVIEW)
            self.window.set_cursor(None)
            self.spinner_view.set_text()
            self.view_initialized = True

    def get_query(self):
        """helper that gets the query for the current category/search mode"""
        # NoDisplay is a specal case
        if self._in_no_display_category():
            return xapian.Query()
        # get current sub-category (or category, but sub-category wins)
        cat_query = None
        if self.apps_subcategory:
            cat_query = self.apps_subcategory.query
        elif self.apps_category:
            cat_query = self.apps_category.query
        # mix category with the search terms and return query
        return self.db.get_query_list_from_search_entry(self.apps_search_term,
                                                        cat_query)
                                                        
    def _in_no_display_category(self):
        """return True if we are in a category with NoDisplay set in the XML"""
        return (self.apps_category and
                self.apps_category.dont_display and
                not self.apps_subcategory and
                not self.apps_search_term)

    def _show_hide_subcategories(self, show_category_applist=False):
        # check if have subcategories and are not in a subcategory
        # view - if so, show it
        if (self.notebook.get_current_page() == self.PAGE_CATEGORY or
            self.notebook.get_current_page() == self.PAGE_APP_DETAILS):
            return
        if (not show_category_applist and
            self.apps_category and
            self.apps_category.subcategories and
            not (self.apps_search_term or self.apps_subcategory)):
            self.subcategories_view.set_subcategory(self.apps_category,
                                                    num_items=len(self.app_view.get_model()))
            self.notebook.set_current_page(self.PAGE_SUBCATEGORY)
        else:
            self.notebook.set_current_page(self.PAGE_APPLIST)

    def update_navigation_button(self):
        """Update the navigation button"""
        if self.apps_category and not self.apps_search_term:
            cat =  self.apps_category.name
            self.navigation_bar.add_with_id(cat,
                                            self.on_navigation_list,
                                            NAV_BUTTON_ID_LIST, 
                                            do_callback=True, 
                                            animate=True)

        elif self.apps_search_term:
            if ',' in self.apps_search_term:
                tail_label = _("Custom List")
            else:
                tail_label = _("Search Results")
            self.navigation_bar.add_with_id(tail_label,
                                            self.on_navigation_search,
                                            NAV_BUTTON_ID_SEARCH, 
                                            do_callback=True,
                                            animate=True)

    # status text woo
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if (self.notebook.get_current_page() == self.PAGE_APP_DETAILS or
            self._in_no_display_category()):
            return ""
        return self._status_text

    def get_current_app(self):
        """return the current active application object"""
        if self.is_category_view_showing():
            return None
        else:
            if self.apps_subcategory:
                return self.current_app_by_subcategory.get(self.apps_subcategory)
            else:
                return self.current_app_by_category.get(self.apps_category)

    def get_current_category(self):
        """ return the current category that is in use or None """
        if self.apps_subcategory:
            return self.apps_subcategory
        elif self.apps_category:
            return self.apps_category
        return None

    def unset_current_category(self):
        """ unset the current showing category, but keep e.g. the current 
            search 
        """
        self.apps_category = None
        self.apps_subcategory = None
        self.navigation_bar.remove_all(do_callback=False, animate=False)
        self.update_navigation_button()

    def _on_transactions_changed(self, *args):
        """internal helper that keeps the action bar up-to-date by
           keeping track of the transaction-started signals
        """
        if self.apps_search_term and ',' in self.apps_search_term:
            self._update_action_bar()

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text and the action
           bar up-to-date by keeping track of the app-list-changed
           signals
        """
        super(AvailablePane, self).on_app_list_changed(pane, length)
        self._show_hide_subcategories()
        self._update_status_text(length)
        self._update_action_bar()

    def _update_status_text(self, length):
        """
        update the text in the status bar
        """
        # SPECIAL CASE: in category page show all items in the DB
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            distro = get_distro()
            if self.apps_filter.get_supported_only():
                query = distro.get_supported_query()
            else:
                query = xapian.Query('')
            enquire = xapian.Enquire(self.db.xapiandb)
            # XD is the term for pkgs that have a desktop file
            enquire.set_query(xapian.Query(xapian.Query.OP_AND_NOT, 
                                           query,
                                           xapian.Query("XD"),
                                           )
                             )
            matches = enquire.get_mset(0, len(self.db))
            length = len(matches)

        if self.apps_search_term and ',' in self.apps_search_term:
            length = len(self.app_view.get_model().apps)
            self._status_text = gettext.ngettext("%(amount)s item",
                                                 "%(amount)s items",
                                                 length) % { 'amount' : length, }
        elif len(self.searchentry.get_text()) > 0:
            self._status_text = gettext.ngettext("%(amount)s matching item",
                                                 "%(amount)s matching items",
                                                 length) % { 'amount' : length, }
        else:
            self._status_text = gettext.ngettext("%(amount)s item available",
                                                 "%(amount)s items available",
                                                 length) % { 'amount' : length, }

    def _update_action_bar(self):
        self._update_action_bar_buttons()
        self.update_show_hide_nonapps()

    def _update_action_bar_buttons(self):
        '''
        update buttons in the action bar to implement the custom package lists feature,
        see https://wiki.ubuntu.com/SoftwareCenter#Custom%20package%20lists
        '''
        appstore = self.app_view.get_model()
        if (appstore and
            self.apps_search_term and
            ',' in self.apps_search_term and
            self.notebook.get_current_page() == self.PAGE_APPLIST):
            appstore = self.app_view.get_model()
            installable = []
            for app in appstore.apps:
                if (app.pkgname in self.cache and
                    not self.cache[app.pkgname].is_installed and
                    app.pkgname not in self.backend.pending_transactions):
                    installable.append(app)
            button_text = gettext.ngettext("Install %(amount)s Item",
                                           "Install %(amount)s Items",
                                            len(installable)) % { 'amount': len(installable), }
            button = self.action_bar.get_button(ACTION_BUTTON_ID_INSTALL)
            if button and installable:
                # Install all already offered. Update offer.
                if button.get_label() != button_text:
                    button.set_label(button_text)
            elif installable:
                # Install all not yet offered. Offer.
                self.action_bar.add_button(ACTION_BUTTON_ID_INSTALL, button_text,
                                           self._install_current_appstore)
            else:
                # Install offered, but nothing to install. Clear offer.
                self.action_bar.remove_button(ACTION_BUTTON_ID_INSTALL)
        else:
            # Ensure button is removed.
            self.action_bar.remove_button(ACTION_BUTTON_ID_INSTALL)
            
    def _install_current_appstore(self):
        '''
        Function that installs all applications displayed in the pane.
        '''
        pkgnames = []
        appnames = []
        iconnames = []
        appstore = self.app_view.get_model()
        for app in appstore.apps:
            if (app.pkgname in self.cache and
                not self.cache[app.pkgname].is_installed and
                app.pkgname not in self.backend.pending_transactions):
                pkgnames.append(app.pkgname)
                appnames.append(app.appname)
                # add iconnames
                doc = self.db.get_xapian_document(app.appname, app.pkgname)
                iconnames.append(self.db.get_iconname(doc))
        self.backend.install_multiple(pkgnames, appnames, iconnames)

    def _show_category_overview(self):
        " helper that shows the category overview "
        # reset category query
        self.apps_category = None
        self.apps_subcategory = None
        # remove pathbar stuff
        self.navigation_bar.remove_all(do_callback=False)
        self.notebook.set_current_page(self.PAGE_CATEGORY)
        self.hide_appview_spinner()
        self.emit("app-list-changed", len(self.db))
        self.searchentry.show()

    def get_app_items_limit(self):
        if self.apps_search_term:
            return DEFAULT_SEARCH_LIMIT
        elif self.apps_category and self.apps_category.item_limit > 0:
            return self.apps_category.item_limit
        return 0

    def _clear_search(self):
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_search_term = ""
        self.navigation_bar.remove_id(NAV_BUTTON_ID_SEARCH)

    @wait_for_apt_cache_ready
    def show_app(self, app):
        """ Display an application in the available_pane """
        cat_of_app = None
        # FIXME: it would be great to extract this code so that
        #        we can use it to show the category in search hits
        #        as well
        for cat in CategoriesView.parse_applications_menu(self.cat_view, APP_INSTALL_PATH):
            if (not cat_of_app and 
                cat.untranslated_name != "New Applications" and 
                cat.untranslated_name != "Featured Applications"):
                if self.db.pkg_in_category(app.pkgname, cat.query):
                    cat_of_app = cat
                    continue
        # FIXME: we need to figure out why it does not work with animate=True
        #        - race ?
        self.navigation_bar.remove_all(animate=False) # animate *must* be false here
        if cat_of_app:
            self.apps_category = cat_of_app
            self.navigation_bar.add_with_id(cat_of_app.name, 
                                            self.on_navigation_list,
                                            NAV_BUTTON_ID_LIST,
                                            do_callback=False,
                                            animate=False)
        else:
            self.apps_category = Category("deb", "deb", None, None, False, True, None)
        self.current_app_by_category[self.apps_category] = app
        details = app.get_details(self.db)
        self.navigation_bar.add_with_id(details.display_name,
                                        self.on_navigation_details,
                                        NAV_BUTTON_ID_DETAILS,
                                        animate=False)
        self.app_details_view.show_app(app)
        self.display_details()

    # callbacks
    def on_cache_ready(self, cache):
        """ refresh the application list when the cache is re-opened """
        # just re-draw in the available pane, nothing but the
        # "is-installed" overlay icon will change when something
        # is installed or removed in the available pane
        self.app_view.queue_draw()

    def on_search_terms_changed(self, widget, new_text):
        """callback when the search entry widget changes"""
        LOG.debug("on_search_terms_changed: %s" % new_text)

        # we got the signal after we already switched to a details
        # page, ignore it
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return

        # yeah for special cases - as discussed on irc, mpt
        # wants this to return to the category screen *if*
        # we are searching but we are not in any category
        if not self.apps_category and not new_text:
            # category activate will clear search etc
            self.apps_search_term = ""
            self.navigation_bar.navigate_up()
            return

        # if the user searches in the "all categories" page, reset the specific
        # category query (to ensure all apps are searched)
        if self.notebook.get_current_page() == self.PAGE_CATEGORY:
            self.apps_category = None
            self.apps_subcategory = None

        # DTRT if the search is reseted
        if not new_text:
            self._clear_search()
        else:
            self.apps_search_term = new_text
            self.apps_limit = DEFAULT_SEARCH_LIMIT
        self.update_navigation_button()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)

    def on_db_reopen(self, db):
        " called when the database is reopened"
        #print "on_db_open"
        self.refresh_apps()
        self.app_details_view.refresh_app()

    def display_category(self):
        self._clear_search()
        self._show_category_overview()
        self.action_bar.clear()
        return

    def display_search(self):
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_PURCHASE)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        if self.app_view.get_model():
            list_length = len(self.app_view.get_model())
            self.emit("app-list-changed", list_length)
        self.searchentry.show()
        return

    def display_list(self):
        self.navigation_bar.remove_id(NAV_BUTTON_ID_SUBCAT)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_PURCHASE)

        if self.apps_subcategory:
            self.apps_subcategory = None
        self.set_category(self.apps_category)
        if self.apps_search_term:
            self._clear_search()
            self.refresh_apps()

        self.notebook.set_current_page(self.PAGE_APPLIST)
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.searchentry.show()
        self.cat_view.stop_carousels()
        
        self._update_action_bar()
        return

    def display_subcat(self):
        if self.apps_search_term:
            self._clear_search()
            self.refresh_apps()
        self.set_category(self.apps_subcategory)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_PURCHASE)
        self.notebook.set_current_page(self.PAGE_SUBCATEGORY)
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.action_bar.clear()
        self.searchentry.show()
        self.cat_view.stop_carousels()
        return

    def display_details(self):
        self.navigation_bar.remove_id(NAV_BUTTON_ID_PURCHASE)
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
        self.action_bar.clear()
        self.cat_view.stop_carousels()
        # we want to re-enable the buy button if this is an app for purchase
        # FIXME:  hacky, find a better approach
        if self.app_details_view.pkg_statusbar.button.get_label() == _(u'Buy\u2026'):
            self.app_details_view.pkg_statusbar.button.set_sensitive(True)
        return
        
    def display_purchase(self):
        self.notebook.set_current_page(self.PAGE_APP_PURCHASE)
        self.searchentry.hide()
        self.action_bar.clear()
        self.cat_view.stop_carousels()
        return
        
    def display_previous_purchases(self):
        self.nonapps_visible = AppStore.NONAPPS_ALWAYS_VISIBLE
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.refresh_apps(query=self.previous_purchases_query)
        self.searchentry.hide()
        self.action_bar.clear()
        self.cat_view.stop_carousels()
        return

    def on_navigation_category(self, pathbar, part):
        """callback when the navigation button with id 'category' is clicked"""
        # clear the search
        self.display_category()
        nav_item = NavigationItem(self, self.display_category)
        self.nav_history.navigate(nav_item)

    def on_navigation_search(self, pathbar, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()
        nav_item = NavigationItem(self, self.display_search)
        self.nav_history.navigate(nav_item)

    def on_navigation_list(self, pathbar, part):
        """callback when the navigation button with id 'list' is clicked"""
        self.display_list()
        nav_item = NavigationItem(self, self.display_list)
        self.nav_history.navigate(nav_item)

    def on_navigation_subcategory(self, pathbar, part):
        self.display_subcat()
        nav_item = NavigationItem(self, self.display_subcat)
        self.nav_history.navigate(nav_item)

    def on_navigation_details(self, pathbar, part):
        """callback when the navigation button with id 'details' is clicked"""
        self.display_details()
        nav_item = NavigationItem(self, self.display_details)
        self.nav_history.navigate(nav_item)
        
    def on_navigation_purchase(self, pathbar, part):
        """callback when the navigation button with id 'purchase' is clicked"""
        self.display_purchase()
        nav_item = NavigationItem(self, self.display_purchase)
        self.nav_history.navigate(nav_item)
        
    def on_navigation_previous_purchases(self, pathbar, part):
        """callback when the navigation button with id 'prev-purchases' is clicked"""
        self.display_previous_purchases()
        nav_item = NavigationItem(self, self.display_previous_purchases)
        self.nav_history.navigate(nav_item)

    def on_subcategory_activated(self, cat_view, category):
        #print cat_view, name, query
        LOG.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.apps_subcategory = category
        self.navigation_bar.add_with_id(
            category.name, self.on_navigation_subcategory, NAV_BUTTON_ID_SUBCAT)

    def on_category_activated(self, cat_view, category):
        """ callback when a category is selected """
        #print cat_view, name, query
        LOG.debug("on_category_activated: %s %s" % (
                category.name, category))
        self.apps_category = category
        self.update_navigation_button()

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        LOG.debug("on_application_selected: '%s'" % app)

        if self.apps_subcategory:
            self.current_app_by_subcategory[self.apps_subcategory] = app
        else:
            self.current_app_by_category[self.apps_category] = app

    def on_nav_back_clicked(self, widget, event):
        self.navhistory_back_action.activate()

    def on_nav_forward_clicked(self, widget, event):
        self.navhistory_forward_action.activate()
        
    def on_show_category_applist(self, widget):
        self._show_hide_subcategories(show_category_applist=True)
        
    def on_previous_purchases_activated(self, query):
        """ called to activate the previous purchases view """
        #print cat_view, name, query
        LOG.debug("on_previous_purchases_activated with query: %s" % query)
        self.previous_purchases_query = query
        self.navigation_bar.remove_all(do_callback=False, animate=False)
        self.navigation_bar.add_with_id(_("Previous Purchases"),
                                          self.on_navigation_previous_purchases,
                                          NAV_BUTTON_ID_PREV_PURCHASES)

    def is_category_view_showing(self):
        """ Return True if we are in the category page or if we display a
            sub-category page
        """
        return (self.notebook.get_current_page() == self.PAGE_CATEGORY or \
                self.notebook.get_current_page() == self.PAGE_SUBCATEGORY)

    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == self.PAGE_APPLIST
        
    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == self.PAGE_APP_DETAILS

    def set_section(self, section):
        self.cat_view.set_section(section)
        self.subcategories_view.set_section(section)
        SoftwarePane.set_section(self, section)
        return

    def set_category(self, category):
        LOG.debug('set_category: %s' % category)

        # apply any category based filters
        if not self.apps_filter:
            self.apps_filter = AppViewFilter(self.db, self.cache)

        if category and category.flags and 'available-only' in category.flags:
            self.apps_filter.set_available_only(True)
        else:
            self.apps_filter.set_available_only(False)

        if category and category.flags and 'not-installed-only' in category.flags:
            self.apps_filter.set_not_installed_only(True)
        else:
            self.apps_filter.set_not_installed_only(False)

        # the rest
        self.update_navigation_button()
        def _cb():
            self.refresh_apps()
            return False
        gobject.timeout_add(1, _cb)
        pass

if __name__ == "__main__":

    from softwarecenter.db.database import StoreDatabase

    #logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir,"icons"))
    icons.append_search_path(os.path.join(datadir,"emblems"))
    # HACK: make it more friendly for local installs (for mpt)
    icons.append_search_path(datadir+"/icons/32x32/status")
    gtk.window_set_default_icon_name("softwarecenter")
    cache = apt.Cache(apt.progress.text.OpProgress())
    cache.ready = True

    # xapian
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    try:
        db = StoreDatabase(pathname, cache)
        db.open()
    except xapian.DatabaseOpeningError:
        # Couldn't use that folder as a database
        # This may be because we are in a bzr checkout and that
        #   folder is empty. If the folder is empty, and we can find the
        # script that does population, populate a database in it.
        if os.path.isdir(pathname) and not os.listdir(pathname):
            from softwarecenter.db.update import rebuild_database
            logging.info("building local database")
            rebuild_database(pathname)
            db = StoreDatabase(pathname, cache)
            db.open()
    except xapian.DatabaseCorruptError, e:
        logging.exception("xapian open failed")
        dialogs.error(None, 
                      _("Sorry, can not open the software database"),
                      _("Please re-install the 'software-center' "
                        "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)

    navhistory_back_action = gtk.Action("navhistory_back_action", "Back", "Back", None)
    navhistory_forward_action = gtk.Action("navhistory_forward_action", "Forward", "Forward", None)
    w = AvailablePane(cache, db, 'Ubuntu', icons, datadir, navhistory_back_action, navhistory_forward_action)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(800,600)
    win.show_all()
    glib.idle_add(w.init_view)

    gtk.main()
