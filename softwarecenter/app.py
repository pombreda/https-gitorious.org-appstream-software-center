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

import atexit
import atk
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

from softwarecenter import Application
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.version import *
from softwarecenter.db.database import StoreDatabase
import softwarecenter.view.dialogs as dialogs

import view.dialogs
from view.viewswitcher import ViewSwitcher, ViewSwitcherList
from view.pendingview import PendingView
from view.installedpane import InstalledPane
from view.channelpane import ChannelPane
from view.availablepane import AvailablePane
from view.softwarepane import SoftwarePane
from view.historypane import HistoryPane
from view.viewmanager import ViewManager

from backend.config import get_config
from backend import get_install_backend

from plugin import PluginManager

# launchpad stuff
from view.logindialog import LoginDialog
from backend.launchpad import GLaunchpad

from distro import get_distro

from apt.aptcache import AptCache
from apt.apthistory import get_apt_history
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
    
    WEBLINK_URL = "http://apt.ubuntu.com/p/%s"
    
    # the size of the icon for dialogs
    APP_ICON_SIZE = 48  # gtk.ICON_SIZE_DIALOG ?

    # FIXME:  REMOVE THIS once launchpad integration is enabled
    #         by default
    def __init__(self, datadir, xapian_base_path, enable_lp_integration=False):
    #def __init__(self, datadir, xapian_base_path):
    
        self._logger = logging.getLogger(__name__)
        self.datadir = datadir
        SimpleGtkbuilderApp.__init__(self, 
                                     datadir+"/ui/SoftwareCenter.ui", 
                                     "software-center")
        gettext.bindtextdomain("software-center", "/usr/share/locale")
        gettext.textdomain("software-center")

        try:
            locale.setlocale(locale.LC_ALL, "")
        except:
            self._logger.exception("setlocale failed")

        # setup dbus and exit if there is another instance already
        # running
        self.setup_dbus_or_bring_other_instance_to_front()
        self.setup_database_rebuilding_listener()
        
        try:
            locale.setlocale(locale.LC_ALL, "")
        except Exception, e:
            self._logger.exception("setlocale failed")

        # distro specific stuff
        self.distro = get_distro()

        # Disable software-properties if it does not exist
        if not os.path.exists("/usr/bin/software-properties-gtk"):
            sources = self.builder.get_object("menuitem_software_sources")
            sources.set_sensitive(False)

        # a main iteration friendly apt cache
        self.cache = AptCache()
        self.cache.connect("cache-broken", self._on_apt_cache_broken)
        self.backend = get_install_backend()
        self.backend.connect("transaction-started", self._on_transaction_started)
        self.backend.connect("transaction-finished", self._on_transaction_finished)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped)
        self.backend.connect("channels-changed", self.on_channels_changed)
        #apt history
        self.history = get_apt_history()
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
                self._logger.info("building local database")
                rebuild_database(pathname)
                self.db = StoreDatabase(pathname, self.cache)
                self.db.open()
        except xapian.DatabaseCorruptError, e:
            self._logger.exception("xapian open failed")
            view.dialogs.error(None, 
                               _("Sorry, can not open the software database"),
                               _("Please re-install the 'software-center' "
                                 "package."))
            # FIXME: force rebuild by providing a dbus service for this
            sys.exit(1)
    
        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path(ICON_PATH)
        self.icons.append_search_path(os.path.join(datadir,"icons"))
        self.icons.append_search_path(os.path.join(datadir,"emblems"))
        # HACK: make it more friendly for local installs (for mpt)
        self.icons.append_search_path(datadir+"/icons/32x32/status")
        with ExecutionTime('Add humanity icon theme to iconpath from SoftwareCenterApp'):
        # add the humanity icon theme to the iconpath, as not all icon themes contain all the icons we need
        # this *shouldn't* lead to any performance regressions
            path = '/usr/share/icons/Humanity'
            if os.path.exists(path):
                for subpath in os.listdir(path):
                    subpath = os.path.join(path, subpath)
                    if os.path.isdir(subpath):
                        for subsubpath in os.listdir(subpath):
                            subsubpath = os.path.join(subpath, subsubpath)
                            if os.path.isdir(subsubpath):
                                self.icons.append_search_path(subsubpath)
        gtk.window_set_default_icon_name("softwarecenter")

        # misc state
        self._block_menuitem_view = False
        self._available_items_for_page = {}
 
        # register view manager and create view panes/widgets
        self.view_manager = ViewManager(self.notebook_view)
        
        # available pane
        self.available_pane = AvailablePane(self.cache,
                                            self.history,
                                            self.db,
                                            self.distro,
                                            self.icons,
                                            datadir,
                                            self.navhistory_back_action,
                                            self.navhistory_forward_action)
        self.available_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                VIEW_PAGE_AVAILABLE)
        self.available_pane.app_view.connect("application-selected",
                                             self.on_app_selected)
        self.available_pane.app_details.connect("application-request-action", 
                                                self.on_application_request_action)
        self.available_pane.app_view.connect("application-request-action", 
                                             self.on_application_request_action)
        self.available_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    VIEW_PAGE_AVAILABLE)
        self.view_manager.register(self.available_pane, VIEW_PAGE_AVAILABLE)

        # channel pane
        self.channel_pane = ChannelPane(self.cache,
                                        self.history,
                                        self.db,
                                        self.distro,
                                        self.icons,
                                        datadir)
        self.channel_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                VIEW_PAGE_CHANNEL)
        self.channel_pane.app_view.connect("application-selected",
                                             self.on_app_selected)
        self.channel_pane.app_details.connect("application-request-action", 
                                              self.on_application_request_action)
        self.channel_pane.app_view.connect("application-request-action", 
                                           self.on_application_request_action)
        self.channel_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    VIEW_PAGE_CHANNEL)
        self.view_manager.register(self.channel_pane, VIEW_PAGE_CHANNEL)
        
        # installed pane
        self.installed_pane = InstalledPane(self.cache,
                                            self.history,
                                            self.db, 
                                            self.distro,
                                            self.icons,
                                            datadir)
        self.installed_pane.app_details.connect("selected", 
                                                self.on_app_details_changed,
                                                VIEW_PAGE_INSTALLED)
        self.installed_pane.app_view.connect("application-selected",
                                             self.on_app_selected)
        self.installed_pane.app_details.connect("application-request-action", 
                                                self.on_application_request_action)
        self.installed_pane.app_view.connect("application-request-action", 
                                             self.on_application_request_action)
        self.installed_pane.connect("app-list-changed", 
                                    self.on_app_list_changed,
                                    VIEW_PAGE_INSTALLED)
        self.view_manager.register(self.installed_pane, VIEW_PAGE_INSTALLED)

        # history pane
        self.history_pane = HistoryPane(self.cache,
                                        self.history,
                                        self.db,
                                        self.distro,
                                        self.icons,
                                        datadir)
        self.history_pane.connect("app-list-changed", 
                                  self.on_app_list_changed,
                                  VIEW_PAGE_HISTORY)
        self.view_manager.register(self.history_pane, VIEW_PAGE_HISTORY)

        # pending view
        self.pending_view = PendingView(self.icons)
        self.view_manager.register(self.pending_view, VIEW_PAGE_PENDING)

        # view switcher
        self.view_switcher = ViewSwitcher(self.view_manager, datadir, self.db, self.cache, self.icons)
        self.scrolledwindow_viewswitcher.add(self.view_switcher)
        self.view_switcher.show()
        self.view_switcher.connect("view-changed", 
                                   self.on_view_switcher_changed)
        self.view_switcher.set_view(VIEW_PAGE_AVAILABLE)

        # launchpad integration help, its ok if that fails
        try:
            import LaunchpadIntegration
            LaunchpadIntegration.set_sourcepackagename("software-center")
            LaunchpadIntegration.add_items(self.menu_help, 1, True, False)
        except Exception, e:
            self._logger.debug("launchpad integration error: '%s'" % e)
            
        # set up accelerator keys for navigation history actions
        accel_group = gtk.AccelGroup()
        self.window_main.add_accel_group(accel_group)
        self.menuitem_go_back.add_accelerator("activate",
                                              accel_group,
                                              ord('['),
                                              gtk.gdk.CONTROL_MASK,
                                              gtk.ACCEL_VISIBLE)
        self.menuitem_go_forward.add_accelerator("activate",
                                                 accel_group,
                                                 ord(']'),
                                                 gtk.gdk.CONTROL_MASK,
                                                 gtk.ACCEL_VISIBLE)

        # default focus
        self.available_pane.searchentry.grab_focus()
        self.window_main.set_size_request(600, 400)

        # setup window name and about information (needs branding)
        name = self.distro.get_app_name()
        self.window_main.set_title(name)
        self.aboutdialog.set_name(name)
        about_description = self.distro.get_app_description()
        self.aboutdialog.set_comments(about_description)

        # about dialog
        self.aboutdialog.connect("response",
                                 lambda dialog, rid: dialog.hide())

        # restore state
        self.config = get_config()
        self.restore_state()

        # atk and stuff
        atk.Object.set_name(self.label_status.get_accessible(), "status_text")
        
        # open plugin manager and load plugins
        self.plugin_manager = PluginManager(self, SOFTWARE_CENTER_PLUGIN_DIR)
        self.plugin_manager.load_plugins()

        # FIXME:  REMOVE THIS once launchpad integration is enabled
        #         by default
        if not enable_lp_integration:
            file_menu = self.builder.get_object("menu1")
            file_menu.remove(self.builder.get_object("separator_login"))
            file_menu.remove(self.builder.get_object("menuitem_login"))

    # callbacks
    def on_app_details_changed(self, widget, app, page):
        self.update_app_status_menu()
        self.update_status_bar()

    def on_app_list_changed(self, pane, new_len, page):
        self._available_items_for_page[page] = new_len
        if self.view_manager.get_active_view() == page:
            self.update_app_list_view()
            self.update_app_status_menu()
            self.update_status_bar()

    def on_app_selected(self, widget, app):
        self.update_app_status_menu()

    def on_window_main_delete_event(self, widget, event):
        if hasattr(self, "glaunchpad"):
            self.glaunchpad.shutdown()
        self.save_state()
        gtk.main_quit()
        
    def on_window_main_key_press_event(self, widget, event):
        if (event.keyval == gtk.gdk.keyval_from_name("BackSpace") and 
            self.active_pane and
            not self.active_pane.searchentry.is_focus()):
            self.active_pane.navigation_bar.navigate_up()
        
    def on_view_switcher_changed(self, view_switcher, view_id, channel):
        self._logger.debug("view_switcher_activated: %s %s" % (view_switcher, view_id))
        # set active pane
        self.active_pane = self.view_manager.get_view_widget(view_id)

        # set menu sensitve
        self.menuitem_view_supported_only.set_sensitive(self.active_pane != None)
        self.menuitem_view_all.set_sensitive(self.active_pane != None)
        # set menu state
        if self.active_pane:
            self._block_menuitem_view = True
            if not self.active_pane.apps_filter:
                self.menuitem_view_all.set_sensitive(False)
                self.menuitem_view_supported_only.set_sensitive(False)
            elif self.active_pane.apps_filter.get_supported_only():
                self.menuitem_view_supported_only.activate()
            else:
                self.menuitem_view_all.activate()
            self._block_menuitem_view = False
        if view_id == VIEW_PAGE_AVAILABLE:
            back_action = self.available_pane.nav_history.navhistory_back_action
            forward_action = self.available_pane.nav_history.navhistory_forward_action
            self.menuitem_go_back.set_sensitive(back_action.get_sensitive())
            self.menuitem_go_forward.set_sensitive(forward_action.get_sensitive())
        else:
            self.menuitem_go_back.set_sensitive(False)
            self.menuitem_go_forward.set_sensitive(False)
        # switch to new page
        self.view_manager.set_active_view(view_id)
        self.update_app_list_view(channel)
        self.update_status_bar()
        self.update_app_status_menu()

    def _on_lp_login(self, lp, token):
        print "_on_lp_login"
        self._lp_login_successful = True
        private_archives = self.glaunchpad.get_subscribed_archives()
        self.view_switcher.get_model().channel_manager.feed_in_private_sources_list_entries(
            private_archives)
            
    def on_application_request_action(self, widget, app, addons_install, addons_remove, action):
        """callback when an app action is requested from the appview,
           if action is "remove", must check if other dependencies have to be
           removed as well and show a dialog in that case
        """
        logging.debug("on_application_action_requested: '%s' %s" % (app, action))
        appdetails = app.get_details(self.db)
        if action == "remove":
            # if we are removing a package, check for dependencies that will
            # also be removed and show a dialog for confirmation
            # generic removal text
            # FIXME: this text is not accurate, we look at recommends as
            #        well as part of the rdepends, but those do not need to
            #        be removed, they just may be limited in functionality
            (primary, button_text) = self.distro.get_removal_warning_text(self.cache,
                                                                          appdetails.pkg,
                                                                          app.name)

            # ask for confirmation if we have rdepends
            depends = self.cache.get_installed_rdepends(appdetails.pkg)
            if depends:
                iconpath = self.get_icon_filename(appdetails.icon, self.APP_ICON_SIZE)
                
                if not dialogs.confirm_remove(None, self.datadir, primary, self.cache,
                                            button_text, iconpath, depends):
                    # for appdetailsview-webkit
                    # self._set_action_button_sensitive(True)

                    self.backend.emit("transaction-stopped")
                    return
            
        # action_func is one of:  "install", "remove", "upgrade", or "apply_changes"
        action_func = getattr(self.backend, action)
        if callable(action_func):
            action_func(app.pkgname, app.appname, appdetails.icon, addons_install, addons_remove)
        else:
            logging.error("Not a valid action in AptdaemonBackend: '%s'" % action)
            
    def get_icon_filename(self, iconname, iconsize):
        iconinfo = self.icons.lookup_icon(iconname, iconsize, 0)
        if not iconinfo:
            iconinfo = self.icons.lookup_icon(MISSING_APP_ICON, iconsize, 0)
        return iconinfo.get_filename()

    # Menu Items
    def on_menuitem_login_activate(self, menuitem):
        self.glaunchpad = GLaunchpad()
        self.glaunchpad.connect("login-successful", self._on_lp_login)
        LoginDialog(self.glaunchpad, self.datadir, parent=self.window_main)
        self.glaunchpad.connect_to_server()
        
    def on_menuitem_install_activate(self, menuitem):
        app = self.active_pane.get_current_app()
        self.on_application_request_action(self, app, APP_ACTION_INSTALL)

    def on_menuitem_remove_activate(self, menuitem):
        app = self.active_pane.get_current_app()
        self.on_application_request_action(self, app, APP_ACTION_REMOVE)
        
    def on_menuitem_close_activate(self, widget):
        gtk.main_quit()

    def on_menu_edit_activate(self, menuitem):
        """
        Check whether the search field is focused and if so, focus some items
        """
        edit_menu_items = [self.menuitem_undo,
                           self.menuitem_redo,
                           self.menuitem_cut, 
                           self.menuitem_copy,
                           self.menuitem_paste,
                           self.menuitem_delete,
                           self.menuitem_select_all,
                           self.menuitem_search]
        for item in edit_menu_items:
            item.set_sensitive(False)
        if (self.active_pane and
            self.active_pane.searchentry.flags() & gtk.VISIBLE):
            # undo, redo, cut, copy, paste, delete, select_all sensitive 
            # if searchentry is focused (and other more specific conditions)
            if self.active_pane.searchentry.is_focus():
                if len(self.active_pane.searchentry._undo_stack) > 1:
                    self.menuitem_undo.set_sensitive(True)
                if len(self.active_pane.searchentry._redo_stack) > 0:
                    self.menuitem_redo.set_sensitive(True)
                bounds = self.active_pane.searchentry.get_selection_bounds()
                if bounds:
                    self.menuitem_cut.set_sensitive(True)
                    self.menuitem_copy.set_sensitive(True)
                self.menuitem_paste.set_sensitive(True)
                if self.active_pane.searchentry.get_text():
                    self.menuitem_delete.set_sensitive(True)
                    self.menuitem_select_all.set_sensitive(True)
            # search sensitive iff searchentry is not focused
            else:
                self.menuitem_search.set_sensitive(True)

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
        app = self.active_pane.get_current_app()
        if app:
            clipboard = gtk.Clipboard()
            clipboard.set_text(self.WEBLINK_URL % app.pkgname)

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
        # Monitor the subprocess regularly
        glib.timeout_add(100, self._poll_software_sources_subprocess, p)

    def _poll_software_sources_subprocess(self, popen):
        ret = popen.poll()
        if ret is None:
            # Keep monitoring
            return True
        # A return code of 1 means that the sources have changed
        if ret == 1:
            self.run_update_cache()
        self.window_main.set_sensitive(True)
        # Stop monitoring
        return False

    def on_menuitem_about_activate(self, widget):
        self.aboutdialog.set_version(VERSION)
        self.aboutdialog.set_transient_for(self.window_main)
        self.aboutdialog.show()

    def on_menuitem_help_activate(self, menuitem):
        # run yelp
        p = subprocess.Popen(["yelp","ghelp:software-center"])
        # collect the exit status (otherwise we leave zombies)
        glib.timeout_add_seconds(1, lambda p: p.poll() == None, p)

    def on_menuitem_view_all_activate(self, widget):
        if (not self._block_menuitem_view and
            self.active_pane.apps_filter.get_supported_only()):
            self.active_pane.apps_filter.set_supported_only(False)
            self.active_pane.refresh_apps()

    def on_menuitem_view_supported_only_activate(self, widget):
        if (not self._block_menuitem_view and
            not self.active_pane.apps_filter.get_supported_only()):
            self.active_pane.apps_filter.set_supported_only(True)
            self.active_pane.refresh_apps()
            
    def on_navhistory_back_action_activate(self, navhistory_back_action):
        self.available_pane.nav_history.nav_back()
        
    def on_navhistory_forward_action_activate(self, navhistory_forward_action):
        self.available_pane.nav_history.nav_forward()
            
    def _ask_and_repair_broken_cache(self):
        # wait until the window window is available
        if self.window_main.props.visible == False:
            glib.timeout_add_seconds(1, self._ask_and_repair_broken_cache)
            return
        if view.dialogs.confirm_repair_broken_cache(self.window_main, self.datadir):
            self.backend.fix_broken_depends()
        
    def _on_apt_cache_broken(self, aptcache):
        self._ask_and_repair_broken_cache()

    def _on_transaction_started(self, backend):
        self.menuitem_install.set_sensitive(False)
        self.menuitem_remove.set_sensitive(False)
            
    def _on_transaction_finished(self, backend, success):
        """ callback when an application install/remove transaction has finished """
        self.cache.open()
        self.update_app_status_menu()

    def _on_transaction_stopped(self, backend):
        """ callback when an application install/remove transaction has stopped """
        self.update_app_status_menu()

    def on_channels_changed(self, backend, res):
        """ callback when the set of software channels has changed """
        self._logger.debug("on_channels_changed %s" % res)
        if res:
            self.db.open()
            # refresh the available_pane views to reflect any changes
            self.available_pane.refresh_apps()
            self.available_pane.update_app_view()
            self.update_app_status_menu()
            self.update_status_bar()

    # helper

    def run_update_cache(self):
        """update the apt cache (e.g. after new sources where added """
        self.backend.reload()

    def update_app_status_menu(self):
        """Helper that updates the 'File' and 'Edit' menu to enable/disable
           install/remove and Copy/Copy weblink
        """
        self._logger.debug("update_app_status_menu")
        # check if we have a pkg for this page
        app = None
        if self.active_pane:
            app = self.active_pane.get_current_app()
        if app is None:
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
            self.menuitem_copy_web_link.set_sensitive(False)
            return False
        # wait for the cache to become ready (if needed)
        if not self.cache.ready:
            glib.timeout_add(100, lambda: self.update_app_status_menu())
            return False
        # update menu items
        pkg_state = None
        error = None
        if self.active_pane.app_details.appdetails:
            pkg_state = self.active_pane.app_details.appdetails.pkg_state
            error = self.active_pane.app_details.appdetails.error
        if self.active_pane.app_view.is_action_in_progress_for_selected_app():
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
        elif pkg_state == PKG_STATE_UPGRADABLE or pkg_state == PKG_STATE_REINSTALLABLE and not error:
            self.menuitem_install.set_sensitive(True)
            self.menuitem_remove.set_sensitive(True)
        elif pkg_state == PKG_STATE_INSTALLED:
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(True)
        elif pkg_state == PKG_STATE_UNINSTALLED and not error:
            self.menuitem_install.set_sensitive(True)
            self.menuitem_remove.set_sensitive(False)
        elif (not pkg_state and 
              not self.active_pane.is_category_view_showing() and 
              app.pkgname in self.cache and 
              not self.active_pane.app_view.is_action_in_progress_for_selected_app() and
              not error):
            pkg = self.cache[app.pkgname]
            installed = bool(pkg.installed)
            self.menuitem_install.set_sensitive(not installed)
            self.menuitem_remove.set_sensitive(installed)
            self.menuitem_copy_web_link.set_sensitive(True)
        else:
            self.menuitem_install.set_sensitive(False)
            self.menuitem_remove.set_sensitive(False)
            self.menuitem_copy_web_link.set_sensitive(False)
        if pkg_state:
            self.menuitem_copy_web_link.set_sensitive(True)
        # return False to ensure that a possible glib.timeout_add ends
        return False

    def update_status_bar(self):
        "Helper that updates the status bar"
        if self.active_pane:
            s = self.active_pane.get_status_text()
        else:
            # FIXME: deal with the pending view status
            s = ""
        self.label_status.set_text(s)
        
    def update_app_list_view(self, channel=None):
        """Helper that updates the app view list.
        """
        if self.active_pane is None:
            return
        if channel is None and self.active_pane.is_category_view_showing():
            return
        if channel:
            self.channel_pane.set_channel(channel)
            self.active_pane.refresh_apps()
        self.active_pane.update_app_view()

    def _on_database_rebuilding_handler(self, is_rebuilding):
        self._logger.debug("_on_database_rebuilding_handler %s" % is_rebuilding)
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
            self._logger.exception("could not get system bus")
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
            self._logger.debug("query for the update-database exception '%s' (probably ok)" % e)

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
            self._logger.exception("could not initiate dbus")
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
            full_pkgname = packages[0]
            # if there is a "/" in the string consider it as tuple
            (pkgname, seperator, appname) = full_pkgname.partition("/")
            app = Application(appname, pkgname)
            self.available_pane.on_application_activated(None, app)
        if len(packages) > 1:
            # turn multiple packages into a search with ","
            # turn off de-duplication
            self.available_pane.apps_filter.set_only_packages_without_applications(False)
            self.available_pane.searchentry.set_text(",".join(packages))
            self.available_pane.notebook.set_current_page(
                self.available_pane.PAGE_APPLIST)

    def restore_state(self):
        if self.config.has_option("general", "size"):
            (x, y) = self.config.get("general", "size").split(",")
            self.window_main.set_default_size(int(x), int(y))
        if (self.config.has_option("general", "maximized") and
            self.config.getboolean("general", "maximized")):
            self.window_main.maximize()
        if (self.config.has_option("general", "available-node-expanded") and
            self.config.getboolean("general", "available-node-expanded")):
            self.view_switcher.expand_available_node()
        if (self.config.has_option("general", "installed-node-expanded") and
            self.config.getboolean("general", "installed-node-expanded")):
            self.view_switcher.expand_installed_node()

    def save_state(self):
        self._logger.debug("save_state")
        # this happens on a delete event, we explicitely save_state() there
        if self.window_main.window is None:
            return
        if not self.config.has_section("general"):
            self.config.add_section("general")
        maximized = self.window_main.window.get_state() & gtk.gdk.WINDOW_STATE_MAXIMIZED
        if maximized:
            self.config.set("general", "maximized", "True")
        else:
            self.config.set("general", "maximized", "False")
            # size only matters when non-maximized
            size = self.window_main.get_size() 
            self.config.set("general","size", "%s, %s" % (size[0], size[1]))
        available_node_expanded = self.view_switcher.is_available_node_expanded()
        if available_node_expanded:
            self.config.set("general", "available-node-expanded", "True")
        else:
            self.config.set("general", "available-node-expanded", "False")
        installed_node_expanded = self.view_switcher.is_installed_node_expanded()
        if installed_node_expanded:
            self.config.set("general", "installed-node-expanded", "True")
        else:
            self.config.set("general", "installed-node-expanded", "False")
        self.config.write()

    def run(self, args):
        self.window_main.show_all()
        # support both "pkg1 pkg" and "pkg1,pkg2" (and pkg1,pkg2 pkg3)
        for (i, arg) in enumerate(args[:]):
            if "," in arg:
                args.extend(arg.split(","))
                del args[i]
        self.show_available_packages(args)
        atexit.register(self.save_state)
        SimpleGtkbuilderApp.run(self)
