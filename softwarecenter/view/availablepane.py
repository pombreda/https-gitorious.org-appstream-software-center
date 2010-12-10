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
import gtk
import logging
import os
import sys
import xapian

from gettext import gettext as _

from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.db.database import SearchQuery
from softwarecenter.distro import get_distro

from appview import AppView, AppStore, AppViewFilter
#from catview_webkit import CategoriesViewWebkit as CategoriesView
from catview_gtk import LobbyViewGtk, SubCategoryViewGtk
from catview import Category, CategoriesView

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

from widgets.backforward import BackForwardButton

from navhistory import *

LOG = logging.getLogger(__name__)

class AvailablePane(SoftwarePane):
    """Widget that represents the available panel in software-center
       It contains a search entry and navigation buttons
    """

    (PAGE_CATEGORY,
     PAGE_SUBCATEGORY,
     PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(4)

    # define ID values for the various buttons found in the navigation bar
    NAV_BUTTON_ID_CATEGORY = "category"
    NAV_BUTTON_ID_LIST     = "list"
    NAV_BUTTON_ID_SUBCAT   = "subcat"
    NAV_BUTTON_ID_DETAILS  = "details"
    NAV_BUTTON_ID_SEARCH   = "search"

    # constant for use in action bar (see _update_action_bar)
    _INSTALL_BTN_ID = 0

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
        # navigation history actions
        self.navhistory_back_action = navhistory_back_action
        self.navhistory_forward_action = navhistory_forward_action
        # state
        self.apps_category = None
        self.apps_subcategory = None
        self.apps_search_term = ""
        self.apps_limit = 0
        self.apps_filter = AppViewFilter(db, cache)
        # the spec says we mix installed/not installed
        #self.apps_filter.set_not_installed_only(True)
        self._status_text = ""
        self.current_app_by_category = {}
        self.current_app_by_subcategory = {}
        self.pane_name = _("Get Software")
        # search mode
        self.custom_list_mode = False
        # install backend
        self.backend.connect("transactions-changed",
                             self._on_transactions_changed)
        # UI
        self._build_ui()

    def _build_ui(self):
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
                                    gtk.Label(self.NAV_BUTTON_ID_SUBCAT))

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

        # app list
        self.notebook.append_page(self.box_app_list,
                                    gtk.Label(self.NAV_BUTTON_ID_LIST))

        self.cat_view.connect("category-selected", self.on_category_activated)
        self.cat_view.connect("application-selected", self.on_application_selected)
        self.cat_view.connect("application-activated", self.on_application_activated)

        # details
        self.notebook.append_page(self.scroll_details, gtk.Label(self.NAV_BUTTON_ID_DETAILS))

        # set status text
        self._update_status_text(len(self.db))

        # home button
        self.navigation_bar.add_with_id(self.pane_name,
                                        self.on_navigation_category,
                                        self.NAV_BUTTON_ID_CATEGORY,
                                        do_callback=True,
                                        animate=False)

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
            self.update_app_view()

    def update_navigation_button(self):
        """Update the navigation button"""
        if self.apps_category and not self.apps_search_term:
            cat =  self.apps_category.name
            self.navigation_bar.add_with_id(cat,
                                            self.on_navigation_list,
                                            self.NAV_BUTTON_ID_LIST, 
                                            do_callback=True, 
                                            animate=True)

        elif self.apps_search_term:
            if self.custom_list_mode:
                tail_label = _("Custom List")
            else:
                tail_label = _("Search Results")
            self.navigation_bar.add_with_id(tail_label,
                                            self.on_navigation_search,
                                            self.NAV_BUTTON_ID_SEARCH, 
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
        if self.custom_list_mode:
            self._update_action_bar()

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the status text and the action
           bar up-to-date by keeping track of the app-list-changed
           signals
        """
        super(AvailablePane, self).on_app_list_changed(pane, length)
        self._update_status_text(length)
        self._update_action_bar()
        self._show_hide_subcategories()

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

        if self.custom_list_mode:
            appstore = self.app_view.get_model()
            existing = len(appstore.existing_apps)
            self._status_text = gettext.ngettext("%(amount)s item",
                                                 "%(amount)s items",
                                                 existing) % { 'amount' : existing, }
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
        update buttons in the action bar
        '''
        appstore = self.app_view.get_model()
        if (appstore and
            self.custom_list_mode and 
            self.apps_search_term):
            appstore = self.app_view.get_model()
            installable = appstore.installable_apps
            button_text = gettext.ngettext("Install %(amount)s Item",
                                           "Install %(amount)s Items",
                                            len(installable)) % { 'amount': len(installable), }
            button = self.action_bar.get_button(self._INSTALL_BTN_ID)
            if button and installable:
                # Install all already offered. Update offer.
                if button.get_label() != button_text:
                    button.set_label(button_text)
            elif installable:
                # Install all not yet offered. Offer.
                self.action_bar.add_button(self._INSTALL_BTN_ID, button_text,
                                           self._install_current_appstore)
            else:
                # Install offered, but nothing to install. Clear offer.
                self.action_bar.remove_button(self._INSTALL_BTN_ID)
        else:
            # Ensure button is removed.
            self.action_bar.remove_button(self._INSTALL_BTN_ID)
            
    def _install_current_appstore(self):
        '''
        Function that installs all applications displayed in the pane.
        '''
        pkgnames = []
        appnames = []
        iconnames = []
        appstore = self.app_view.get_model()
        for app in appstore.installable_apps:
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
        self.cat_view.start_carousels()
        self.emit("app-list-changed", len(self.db))
        self.searchentry.show()

    def get_app_items_limit(self):
        if self.apps_search_term:
            return DEFAULT_SEARCH_LIMIT
        elif self.apps_category and self.apps_category.item_limit > 0:
            return self.apps_category.item_limit
        return 0

    def _get_sort_mode(self):
        if self.apps_search_term:
            return SORT_BY_SEARCH_RANKING
        elif self.apps_category:
            return self.apps_category.sortmode
        return SORT_BY_ALPHABET

    def _clear_search(self):
        self.searchentry.clear_with_no_signal()
        self.apps_limit = 0
        self.apps_search_term = ""
        self.custom_list_mode = False
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_SEARCH)

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
            self.navigation_bar.add_with_id(cat_of_app.name, self.on_navigation_list, "list", do_callback=False, animate=True)
        else:
            self.apps_category = Category("deb", "deb", None, None, False, True, None)
        self.current_app_by_category[self.apps_category] = app
        details = app.get_details(self.db)
        self.navigation_bar.add_with_id(details.display_name,
                                        self.on_navigation_details,
                                        "details",
                                        animate=True)
        self.app_details.show_app(app)
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
            # enter custom list mode if search has non-trailing
            # comma per custom list spec.
            self.custom_list_mode = "," in new_text.rstrip(',')
        self.update_navigation_button()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)

    def on_db_reopen(self, db):
        " called when the database is reopened"
        #print "on_db_open"
        self.refresh_apps()
        self.app_details.refresh_app()

    def display_category(self):
        self._clear_search()
        self._show_category_overview()
        self.action_bar.clear()
        return

    def display_search(self):
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        if self.app_view.get_model():
            list_length = len(self.app_view.get_model())
            self.emit("app-list-changed", list_length)
        self.searchentry.show()
        return

    def display_list(self):
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_SUBCAT)
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)

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
        self.navigation_bar.remove_id(self.NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_SUBCATEGORY)
        # do not emit app-list-changed here, this is done async when
        # the new model is ready
        self.action_bar.clear()
        self.searchentry.show()
        self.cat_view.stop_carousels()
        return

    def display_details(self):
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
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

    def on_subcategory_activated(self, cat_view, category):
        #print cat_view, name, query
        LOG.debug("on_subcategory_activated: %s %s" % (
                category.name, category))
        self.apps_subcategory = category
        self.navigation_bar.add_with_id(
            category.name, self.on_navigation_subcategory, self.NAV_BUTTON_ID_SUBCAT)

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

    def is_category_view_showing(self):
        """ Return True if we are in the category page or if we display a
            sub-category page
        """
        return (self.notebook.get_current_page() == self.PAGE_CATEGORY or \
                self.notebook.get_current_page() == self.PAGE_SUBCATEGORY)

    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == self.PAGE_APPLIST

    def set_section(self, section):
        self.cat_view.set_section(section)
        self.subcategories_view.set_section(section)
        SoftwarePane.set_section(self, section)
        return

    def set_category(self, category):
        #print "set_category", category
        #import traceback
        #traceback.print_stack()
        self.update_navigation_button()
        def _cb():
            self.refresh_apps()
            # this is already done earlier
            #self.notebook.set_current_page(self.PAGE_APPLIST)
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
    import apt
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
        view.dialogs.error(None, 
                           _("Sorry, can not open the software database"),
                           _("Please re-install the 'software-center' "
                             "package."))
        # FIXME: force rebuild by providing a dbus service for this
        sys.exit(1)

    w = AvailablePane(cache, db, 'Ubuntu', icons, datadir, None, None)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(500,400)
    win.show_all()

    gtk.main()

