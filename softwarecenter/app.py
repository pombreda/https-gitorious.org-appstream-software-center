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
import aptdaemon
import atexit
import locale
import dbus
import dbus.service
import gettext
import locale
import logging
import glib
import gtk
import os
import subprocess
import sys
import xapian

from SimpleGtkbuilderApp import SimpleGtkbuilderApp

from softwarecenter.enums import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase

import view.dialogs
from view.viewswitcher import ViewSwitcher, ViewSwitcherList
from view.pendingview import PendingView
from view.installedpane import InstalledPane
from view.availablepane import AvailablePane
from view.softwarepane import SoftwarePane

from backend.config import get_config

from distro import get_distro

from apt.aptcache import AptCache
from gettext import gettext as _

class SoftwarecenterDbusController(dbus.service.Object):
    """ 
    This is a helper to provide the SoftwarecenterIFace
    
    It provides 
    """
    def __init__(self, parent, bus_name,
                 object_path='/com/ubuntu/Softwarecenter'):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.parent = parent

    @dbus.service.method('com.ubuntu.SoftwarecenterIFace')
    def bringToFront(self):
        self.parent.window_main.present()
        return True

class SoftwareCenterApp(SimpleGtkbuilderApp):
    
    (NOTEBOOK_PAGE_AVAILABLE,
     NOTEBOOK_PAGE_INSTALLED,
     NOTEBOOK_PAGE_SEPARATOR_1,
     NOTEBOOK_PAGE_PENDING) = range(4)

    WEBLINK_URL = "http://apt.ubuntu.com/p/%s"

    def __init__(self, datadir, xapian_base_path):
        SimpleGtkbuilderApp.__init__(self, 
                                     datadir+"/ui/SoftwareCenter.ui", 
                                     "software-center")
        gettext.bindtextdomain("software-center", "/usr/share/locale")
        gettext.textdomain("software-center")

        try:
            locale.setlocale(locale.LC_ALL, "")
        except:
            logging.exception("setlocale failed")

        # setup dbus and exit if there is another instance already
        # running
        self.setup_dbus_or_bring_other_instance_to_front()
        self.setup_database_rebuilding_listener()
        
        try:
            locale.setlocale(locale.LC_ALL, "")
        except Exception, e:
            logging.exception("setlocale failed")

        # distro specific stuff
        self.distro = get_distro()

        # a main iteration friendly apt cache
        self.cache = AptCache()

        # xapian
        pathname = os.path.join(xapian_base_path, "xapian")
        try:
            self.db = StoreDatabase(pathname, self.cache)
            self.db.open()
        except xapian.DatabaseOpeningError:
            # Couldn't use that folder as a database
            # This may be because we are in a bzr checkout and that
            #   folder is empty. If the folder is empty, and we can find the
            # script that does population, populate a database in it.
            if os.path.isdir(pathname) and not os.listdir(pathname):
                from softwarecenter.db.update import rebuild_database
                logging.info("building local database")
                rebuild_database(pathname)
                self.db = StoreDatabase(pathname, self.cache)
                self.db.open()
        except xapian.DatabaseCorruptError, e:
            logging.exception("xapian open failed")
            view.dialogs.error(None, 
                               _("Sorry, can not open the software database"),
                               _("Please re-install the 'software-center' "
                                 "package."))
            # FIXME: force rebuild by providing a dbus service for this
            sys.exit(1)
    
        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path(ICON_PATH)
        self.icons.append_search_path(SOFTWARE_CENTER_ICON_PATH)
        # HACK: make it more friendly for local installs (for mpt)
        self.icons.append_search_path(datadir+"/icons/32x32/status")
        gtk.window_set_default_icon_name("softwarecenter")

        # misc state
        self._pending_transactions = 0
        self._block_menuitem_view = False
        self._available_items_for_page = {}
        # FIXME: make this all part of a application object
        self._selected_pkgname_for_page = {}
        self._selected_appname_for_page = {}

        # available pane
        self.available_pane = AvailablePane(self.cache, self.db,
                                            self.distro,
                                            self.icons, datadir)
        self.available_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                self.NOTEBOOK_PAGE_AVAILABLE)
        self.available_pane.app_view.connect("application-selected",
                                             self.on_app_selected,
                                             self.NOTEBOOK_PAGE_AVAILABLE)
#        self.available_pane.connect("category-view-selected",
#                                    self.on_category_view_selected)
        self.available_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    self.NOTEBOOK_PAGE_AVAILABLE)
        self.alignment_available.add(self.available_pane)

        # installed pane
        self.installed_pane = InstalledPane(self.cache, self.db,
                                            self.distro,
                                            self.icons, datadir)
        self.installed_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                self.NOTEBOOK_PAGE_INSTALLED)
        self.installed_pane.app_view.connect("application-selected",
                                             self.on_app_selected,
                                             self.NOTEBOOK_PAGE_INSTALLED)
        self.installed_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    self.NOTEBOOK_PAGE_INSTALLED)
        self.alignment_installed.add(self.installed_pane)

        # pending view
        self.pending_view = PendingView(self.icons)
        self.scrolledwindow_transactions.add(self.pending_view)

        # view switcher
        self.view_switcher = ViewSwitcher(datadir, self.icons)
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()
        self.view_switcher.connect("view-changed", 
                                   self.on_view_switcher_changed)
        self.view_switcher.model.connect("transactions-changed", 
                                   self.on_view_switcher_transactions_changed)
        self.view_switcher.set_view(ViewSwitcherList.ACTION_ITEM_AVAILABLE)

        # launchpad integration help, its ok if that fails
        try:
            import LaunchpadIntegration
            LaunchpadIntegration.set_sourcepackagename("software-center")
            LaunchpadIntegration.add_items(self.menu_help, 1, True, False)
        except Exception, e:
            logging.debug("launchpad integration error: '%s'" % e)

        # default focus
        self.available_pane.searchentry.grab_focus()
        
        #should we maximize?
        self.config = get_config()
        if self.config.has_option("general", "maximized"):
            self.window_state = self.config.getboolean("general", "maximized")
        else:
            self.window_state = False
        if self.window_state:
            self.window_main.maximize()

    # callbacks
    def on_app_details_changed(self, widget, appname, pkgname, page):
        self._selected_pkgname_for_page[page] = pkgname
        self._selected_appname_for_page[page] = appname
        self.update_app_status_menu()
        self.update_status_bar()

    def on_app_list_changed(self, pane, new_len, page):
        self._available_items_for_page[page] = new_len
        if self.notebook_view.get_current_page() == page:
#            self.menuitem_install.set_sensitive(False)
#            self.menuitem_remove.set_sensitive(False)
#            self.menuitem_copy_web_link.set_sensitive(False)
            self.update_app_view()
            self.update_app_status_menu()
            self.update_status_bar()

    def on_app_selected(self, widget, appname, pkgname, page):
        print ">> called on_app_selected with appname: %s" % (appname)
        self._selected_appname_for_page[page] = appname
        self._selected_pkgname_for_page[page] = pkgname
        self.update_app_status_menu()
        self.menuitem_copy.set_sensitive(True)

#    def on_category_view_selected(self, widget):
#        self.menuitem_install.set_sensitive(False)
#        self.menuitem_remove.set_sensitive(False)
#        self.menuitem_copy_web_link.set_sensitive(False)

    def on_window_main_delete_event(self, widget, event):
        gtk.main_quit()
        
    def on_view_switcher_transactions_changed(self, view_switcher, pending_nr):
        # if the pending number drops to zero check if we should switch
        # to the previous view
        if pending_nr == 0 and self._view_before_pending_switch is not None:
            if self.view_switcher.get_view() is None:
                self.view_switcher.set_view(self._view_before_pending_switch)
            self._view_before_pending_switch = None
        # the spec says that on the first transaction it should auto-switch
        # to the progress view
        elif pending_nr > 0 and self._pending_transactions == 0:
            self._view_before_pending_switch = self.view_switcher.get_view()
            self.view_switcher.set_view(ViewSwitcherList.ACTION_ITEM_PENDING)
        self._pending_transactions = pending_nr

    def on_view_switcher_changed(self, view_switcher, action):
        logging.debug("view_switcher_activated: %s %s" % (view_switcher,action))
        if action == self.NOTEBOOK_PAGE_AVAILABLE:
            self.active_pane = self.available_pane
        elif action == self.NOTEBOOK_PAGE_INSTALLED:
            self.active_pane = self.installed_pane
        elif action == self.NOTEBOOK_PAGE_PENDING:
            self.active_pane = None
        elif action == self.NOTEBOOK_PAGE_SEPARATOR_1:
            # do nothing
            return
        else:
            assert False, "Not reached"
        # set menu sensitve
        self.menuitem_view_supported_only.set_sensitive(self.active_pane != None)
        self.menuitem_view_all.set_sensitive(self.active_pane != None)
        # set menu state
        if self.active_pane:
            self._block_menuitem_view = True
            if self.active_pane.apps_filter.get_supported_only():
                self.menuitem_view_supported_only.activate()
            else:
                self.menuitem_view_all.activate()
            self._block_menuitem_view = False
        # switch to new page
        self.notebook_view.set_current_page(action)
        self.update_app_view()
        self.update_status_bar()
        self.update_app_status_menu()

    # Menu Items
    def on_menuitem_install_activate(self, menuitem):
        page = self.notebook_view.get_current_page() #### do this on a select in the table!
        appname = self._selected_appname_for_page[page]
        pkgname = self._selected_pkgname_for_page[page]
        self.active_pane.app_details.init_app(appname, pkgname)
        self.active_pane.app_details.install()

    def on_menuitem_remove_activate(self, menuitem):
        page = self.notebook_view.get_current_page()
        appname = self._selected_appname_for_page[page]
        pkgname = self._selected_pkgname_for_page[page]
        self.active_pane.app_details.init_app(appname, pkgname)
        self.active_pane.app_details.remove()
        
    def on_menuitem_close_activate(self, widget):
        gtk.main_quit()

    def on_menu_edit_activate(self, menuitem):
        """
        Check whether the search field is focused and if so, focus some items
        """
        if self.active_pane:
            state = self.active_pane.searchentry.is_focus()
        else:
            state = False
        edit_menu_items = [self.menuitem_undo, 
                           self.menuitem_redo, 
                           self.menuitem_cut, 
                           self.menuitem_copy, 
                           self.menuitem_paste, 
                           self.menuitem_delete, 
                           self.menuitem_select_all]
        for item in edit_menu_items:
            item.set_sensitive(state)

    def on_menuitem_undo_activate(self, menuitem):
        self.active_pane.searchentry.undo()
        
    def on_menuitem_redo_activate(self, menuitem):
        self.active_pane.searchentry.redo()

    def on_menuitem_cut_activate(self, menuitem):
        self.active_pane.searchentry.cut_clipboard()

    def on_menuitem_copy_activate(self, menuitem):
        self.active_pane.searchentry.copy_clipboard()

    def on_menuitem_paste_activate(self, menuitem):
        self.active_pane.searchentry.paste_clipboard()

    def on_menuitem_delete_activate(self, menuitem):
        self.active_pane.searchentry.set_text("")

    def on_menuitem_select_all_activate(self, menuitem):
        self.active_pane.searchentry.select_region(0, -1)

    def on_menuitem_copy_web_link_activate(self, menuitem):
        page = self.notebook_view.get_current_page()
        try:
            pkg = self._selected_pkgname_for_page[page]
        except KeyError, e:
            return
        clipboard = gtk.Clipboard()
        clipboard.set_text(self.WEBLINK_URL % pkg)

    def on_menuitem_search_activate(self, widget):
        if self.active_pane:
            self.active_pane.searchentry.grab_focus()
            self.active_pane.searchentry.select_region(0, -1)

    def on_menuitem_software_sources_activate(self, widget):
        #print "on_menu_item_software_sources_activate"
        self.window_main.set_sensitive(False)
        # run software-properties-gtk
        p = subprocess.Popen(
            ["gksu",
             "--desktop", "/usr/share/applications/software-properties.desktop",
             "--",
             "/usr/bin/software-properties-gtk", 
             "-n", 
             "-t", str(self.window_main.window.xid)])
        # wait for it to finish
        ret = None
        while ret is None:
            while gtk.events_pending():
                gtk.main_iteration()
            ret = p.poll()
        # return code of 1 means that it changed
        if ret == 1:
            self.run_update_cache()
        self.window_main.set_sensitive(True)

    def on_menuitem_about_activate(self, widget):
        self.aboutdialog.set_version(VERSION)
        self.aboutdialog.run()
        self.aboutdialog.hide()

    def on_menuitem_help_activate(self, menuitem):
        # run yelp
        p = subprocess.Popen(["yelp","ghelp:software-center"])
        # collect the exit status (otherwise we leave zombies)
        glib.timeout_add(1000, lambda p: p.poll() == None, p)

    def on_menuitem_view_all_activate(self, widget):
        if self._block_menuitem_view:
            return
        self.active_pane.apps_filter.set_supported_only(False)
        self.active_pane.refresh_apps()

    def on_menuitem_view_supported_only_activate(self, widget):
        if self._block_menuitem_view: 
            return
        self.active_pane.apps_filter.set_supported_only(True)
        self.active_pane.refresh_apps()
        
    def on_window_main_window_state_event(self, widget, event):
        self.window_state = event.new_window_state.value_names

    # helper

    # FIXME: move the two functions below into generic code
    #        and share that with the appdetailsview
    def _on_trans_finished(self, trans, enum):
        """callback when a aptdaemon transaction finished"""
        if enum == aptdaemon.enums.EXIT_FAILED:
            excep = trans.get_error()
            msg = "%s: %s\n%s\n\n%s" % (
                   _("ERROR"),
                   aptdaemon.enums.get_error_string_from_enum(excep.code),
                   aptdaemon.enums.get_error_description_from_enum(excep.code),
                   excep.details)
            print msg
        # re-open cache and refresh app display
        self.cache.open()
    def run_update_cache(self):
        """update the apt cache (e.g. after new sources where added """
        aptd_client = aptdaemon.client.AptClient()
        trans = aptd_client.update_cache(exit_handler=self._on_trans_finished)
        try:
            trans.run()
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name == "org.freedesktop.PolicyKit.Error.NotAuthorized":
                pass
            else:
                raise

    def update_app_status_menu(self):
        """Helper that updates the 'File' and 'Edit' menu to enable/disable
           install/remove and Copy/Copy weblink
        """
        logging.debug("update_app_status_menu")
        # check if we have a pkg for this page
        page = self.notebook_view.get_current_page()
        try:
            pkgname = self._selected_pkgname_for_page[page]
        except KeyError, e:
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
            self.menuitem_copy_web_link.set_sensitive(False)
            return False
        # wait for the cache to become ready (if needed)
        if not self.cache.ready:
            glib.timeout_add(100, lambda: self.update_app_status_menu())
            return False
        # if the pkg is not in the cache, clear menu
        if not self.cache.has_key(pkgname):
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
            self.menuitem_copy_web_link.set_sensitive(False)
        # update File menu status
        print ">> self.active_pane.is_category_view_showing()):"
        print self.active_pane.is_category_view_showing()
        if not self.active_pane.is_category_view_showing() and self.cache.has_key(pkgname):
            pkg = self.cache[pkgname]
            installed = bool(pkg.installed)
            self.menuitem_install.set_sensitive(not installed)
            self.menuitem_remove.set_sensitive(installed)
            self.menuitem_copy_web_link.set_sensitive(True)
        else:
            print ">> Category view is showing so reset the menu items"
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
            self.menuitem_copy_web_link.set_sensitive(False)
        # return False to ensure that a possible glib.timeout_add ends
        return False

    def update_status_bar(self):
        "Helper that updates the status bar"
        page = self.notebook_view.get_current_page()
        if self.active_pane:
            s = self.active_pane.get_status_text()
        else:
            # FIXME: deal with the pending view status
            s = ""
        self.label_status.set_text(s)
        
    def update_app_view(self):
        """Helper that updates the appview list.  If no application is selected,
           the first application in the list is selected, else, the selection
           is unchanged.
        """
        print ">>called update_app_view()"
        if self.active_pane is not None and not self.active_pane.is_category_view_showing():
            self.active_pane.update_view()

    def _on_database_rebuilding_handler(self, is_rebuilding):
        logging.debug("_on_database_rebuilding_handler %s" % is_rebuilding)
        self._database_is_rebuilding = is_rebuilding
        self.window_rebuilding.set_transient_for(self.window_main)
        self.window_rebuilding.set_title("")
        self.window_main.set_sensitive(not is_rebuilding)
        # show dialog about the rebuilding status
        if is_rebuilding:
            self.window_rebuilding.show()
        else:
            # we need to reopen when the database finished updating
            self.db.reopen()
            self.window_rebuilding.hide()

    def setup_database_rebuilding_listener(self):
        """
        Setup system bus listener for database rebuilding
        """
        self._database_is_rebuilding = False
        # get dbus
        try:
            bus = dbus.SystemBus()
        except:
            logging.exception("could not get system bus")
            return
        # check if its currently rebuilding (most likely not, so we
        # just ignore errors from dbus because the interface
        try:
            proxy_obj = bus.get_object("com.ubuntu.Softwarecenter",
                                       "/com/ubuntu/Softwarecenter")
            iface = dbus.Interface(proxy_obj, "com.ubuntu.Softwarecenter")
            res = iface.IsRebuilding()
            self._on_database_rebuilding_handler(res)
        except Exception ,e:
            logging.debug("query for the update-database exception '%s' (probably ok)" % e)

        # add signal handler
        bus.add_signal_receiver(self._on_database_rebuilding_handler,
                                "DatabaseRebuilding",
                                "com.ubuntu.Softwarecenter")

    def setup_dbus_or_bring_other_instance_to_front(self):
        """ 
        This sets up a dbus listener
        """
        try:
            bus = dbus.SessionBus()
        except:
            logging.exception("could not initiate dbus")
            return
        # if there is another Softwarecenter running bring it to front
        # and exit, otherwise install the dbus controller
        try:
            proxy_obj = bus.get_object('com.ubuntu.Softwarecenter', 
                                       '/com/ubuntu/Softwarecenter')
            iface = dbus.Interface(proxy_obj, 'com.ubuntu.SoftwarecenterIFace')
            iface.bringToFront()
            sys.exit()
        except dbus.DBusException, e:
            bus_name = dbus.service.BusName('com.ubuntu.Softwarecenter',bus)
            self.dbusControler = SoftwarecenterDbusController(self, bus_name)

    def show_available_packages(self, packages):
        """ Show packages given as arguments in the available_pane
            If the list of packages is only one element long show that,
            otherwise turn it into a comma seperated search
        """
        if len(packages) == 1:
            # show a single package
            pkg_name = packages[0]
            # FIXME: this currently only works with pkg names for apps
            #        it needs to perform a search because a App name
            #        is (in general) not unique
            self.available_pane.app_details.show_app("", pkg_name)
            self.available_pane.notebook.set_current_page(
                self.available_pane.PAGE_APP_DETAILS)
        if len(packages) > 1:
            # turn multiple packages into a search with ","
            # turn off de-duplication
            self.available_pane.apps_filter.set_only_packages_without_applications(False)
            self.available_pane.searchentry.set_text(",".join(packages))
            self.available_pane.notebook.set_current_page(
                self.available_pane.PAGE_APPLIST)

    def save_state(self):
        logging.debug("save_state")
        if self.window_state == ['GDK_WINDOW_STATE_MAXIMIZED']:
            self.config.set("general", "maximized", "True")
        else:
            self.config.set("general", "maximized", "False")
        self.config.write()

    def run(self, args):
        self.window_main.show_all()
        self.show_available_packages(args)
        atexit.register(self.save_state)
        SimpleGtkbuilderApp.run(self)



