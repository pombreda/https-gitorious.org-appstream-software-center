# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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
import dbus
import dbus.service
import gettext
import logging
import glib
import gtk
import os
import subprocess
import sys
import xapian

from SimpleGtkbuilderApp import SimpleGtkbuilderApp

try:
    from softwarestore.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from softwarestore.enums import *

from view.viewswitcher import ViewSwitcher, ViewSwitcherList
from view.pendingview import PendingView
from view.installedpane import InstalledPane
from view.availablepane import AvailablePane

from apt.aptcache import AptCache

from gettext import gettext as _

class SoftwareStoreDbusController(dbus.service.Object):
    """ 
    This is a helper to provide the SoftwareStoreIFace
    
    It provides 
    """
    def __init__(self, parent, bus_name,
                 object_path='/com/ubuntu/SoftwareStore'):
        dbus.service.Object.__init__(self, bus_name, object_path)
        self.parent = parent

    @dbus.service.method('com.ubuntu.SoftwareStoreIFace')
    def bringToFront(self):
        self.parent.window_main.present()
        return True

class SoftwareStoreApp(SimpleGtkbuilderApp):
    
    (NOTEBOOK_PAGE_AVAILABLE,
     NOTEBOOK_PAGE_INSTALLED,
     NOTEBOOK_PAGE_PENDING) = range(3)

    WEBLINK_URL = "http://apt.ubuntu.com/p/%s"

    def __init__(self, datadir):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/SoftwareStore.ui")

        # setup dbus and exit if there is another instance already
        # running
        self.setup_dbus_or_bring_other_instance_to_front()
        
        # xapian
        xapian_base_path = XAPIAN_BASE_PATH
        pathname = os.path.join(xapian_base_path, "xapian")
        self.xapiandb = xapian.Database(pathname)
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self.xapiandb)
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        #self.xapian_parser.add_boolean_prefix("section", "AS")

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path(ICON_PATH)
        # HACK: make it more friendly for local installs (for mpt)
        self.icons.append_search_path(datadir+"/icons/32x32/status")
        
        # a main iteration friendly apt cache
        self.cache = AptCache()

        # misc state
        self._block_menuitem_view = False
        self._available_items_for_page = {}
        # FIXME: make this all part of a application object
        self._selected_pkgname_for_page = {}
        self._selected_appname_for_page = {}

        # available pane
        self.available_pane = AvailablePane(self.cache, self.xapiandb,
                                            self.icons, datadir)
        self.available_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                self.NOTEBOOK_PAGE_AVAILABLE)
        self.available_pane.app_view.connect("application-selected",
                                             self.on_app_selected,
                                             self.NOTEBOOK_PAGE_AVAILABLE)
        self.available_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    self.NOTEBOOK_PAGE_AVAILABLE)
        self.alignment_available.add(self.available_pane)

        # installed pane
        self.installed_pane = InstalledPane(self.cache, self.xapiandb,
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
        self.view_switcher.set_view(ViewSwitcherList.ACTION_ITEM_AVAILABLE)

        # launchpad integration help, its ok if that fails
        try:
            import LaunchpadIntegration
            LaunchpadIntegration.set_sourcepackagename("software-store")
            LaunchpadIntegration.add_items(self.menu_help, 1, True, False)
        except Exception, e:
            logging.debug("launchpad integration error: '%s'" % e)

        # default focus
        self.available_pane.cat_view.grab_focus()

    # callbacks
    def on_app_details_changed(self, widget, appname, pkgname, page):
        #print widget, appname, pkg, page
        self._selected_pkgname_for_page[page] = pkgname
        self._selected_appname_for_page[page] = appname
        self.update_app_status_menu()
        
    def on_app_list_changed(self, pane, new_len, page):
        self._available_items_for_page[page] = new_len
        if self.notebook_view.get_current_page() == page:
            self.update_status_bar()

    def on_app_selected(self, widget, appname, pkgname, page):
        self._selected_appname_for_page[page] = appname
        self._selected_pkgname_for_page[page] = pkgname
        self.menuitem_copy.set_sensitive(True)
        self.menuitem_copy_web_link.set_sensitive(True)

    def on_menuitem_help_activate(self, menuitem):
        # run yelp
        p = subprocess.Popen(["yelp","ghelp:software-store"])
        # collect the exit status (otherwise we leave zombies)
        glib.timeout_add(1000, lambda p: p.poll() == None, p)

    def on_menuitem_close_activate(self, widget):
        gtk.main_quit()

    def on_menuitem_about_activate(self, widget):
        #print "about"
        self.aboutdialog.run()
        self.aboutdialog.hide()

    def on_window_main_delete_event(self, widget, event):
        gtk.main_quit()

    def on_view_switcher_changed(self, view_switcher, action):
        logging.debug("view_switcher_activated: %s %s" % (view_switcher,action))
        if action == self.NOTEBOOK_PAGE_AVAILABLE:
            self.active_pane = self.available_pane
        elif action == self.NOTEBOOK_PAGE_INSTALLED:
            self.active_pane = self.installed_pane
        elif action == self.NOTEBOOK_PAGE_PENDING:
            self.active_pane = None
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
        self.update_status_bar()
        self.update_app_status_menu()

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

    def on_menuitem_search_activate(self, widget):
        #print "on_menuitem_search_activate"
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

    def on_menuitem_install_activate(self, menuitem):
        self.active_pane.app_details.install()

    def on_menuitem_remove_activate(self, menuitem):
        self.active_pane.app_details.remove()

    def on_menuitem_copy_activate(self, menuitem):
        page = self.notebook_view.get_current_page()
        try:
            app = self._selected_appname_for_page[page]
        except KeyError, e:
            return
        clipboard = gtk.Clipboard()
        clipboard.set_text(app)

    def on_menuitem_copy_web_link_activate(self, menuitem):
        page = self.notebook_view.get_current_page()
        try:
            pkg = self._selected_pkgname_for_page[page]
        except KeyError, e:
            return
        clipboard = gtk.Clipboard()
        clipboard.set_text(self.WEBLINK_URL % pkg)

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
            self.menuitem_copy.set_sensitive(False)
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
        pkg = self.cache[pkgname]
        installed = bool(pkg.installed)
        self.menuitem_install.set_sensitive(not installed)
        self.menuitem_remove.set_sensitive(installed)
        # return False to ensure that a possible glib.timeout_add ends
        return False

    def update_status_bar(self):
        "Helper that updates the status bar"
        page = self.notebook_view.get_current_page()
        try:
            new_len = self._available_items_for_page[page]
            s = gettext.ngettext("%s item available",
                                 "%s items available",
                                 new_len) % new_len
        except KeyError, e:
            s = ""
        self.label_status.set_text(s)

    def setup_dbus_or_bring_other_instance_to_front(self):
        """ 
        This sets up a dbus listener
        """
        try:
            bus = dbus.SessionBus()
        except:
            logging.warn("could not initiate dbus")
            return
        # if there is another SoftwareStore running bring it to front
        # and exit, otherwise install the dbus controller
        try:
            proxy_obj = bus.get_object('com.ubuntu.SoftwareStore', 
                                       '/com/ubuntu/SoftwareStore')
            iface = dbus.Interface(proxy_obj, 'com.ubuntu.SoftwareStoreIFace')
            iface.bringToFront()
            sys.exit()
        except dbus.DBusException, e:
            bus_name = dbus.service.BusName('com.ubuntu.SoftwareStore',bus)
            self.dbusControler = SoftwareStoreDbusController(self, bus_name)

    def run(self):
        self.window_main.show_all()
        SimpleGtkbuilderApp.run(self)

    #FIXME: dead-code in multi-view
    def on_button_home_clicked(self, widget):
        logging.debug("on_button_home_clicked")
        # we get the clicked signal when the radio-group toggles
        # so we do not react unless we were not already pressed in
        if not widget.get_active():
            return
        self.apps_category_query = None
        # HACK: ensure that no signal term-changed is send, otherwise
        #       self.on_search_entry_changed() is called and that
        #       moves to a new notebook page 
        # FIXME: deal with it in a cleaner way
        self.entry_search.clear_with_no_signal()
        self.change_notebook_view(self.NOTEBOOK_PAGE_CATEGORIES)


