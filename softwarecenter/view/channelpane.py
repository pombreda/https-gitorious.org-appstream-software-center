# Copyright (C) 2010 Canonical
#
# Authors:
#  Michael Vogt
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

import apt
import gettext
import gtk
import logging
import os
import sys
import xapian
import gobject

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.enums import *
from softwarecenter.utils import wait_for_apt_cache_ready

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane

LOG = logging.getLogger(__name__)

class ChannelPane(SoftwarePane):
    """Widget that represents the channel pane for display of
       individual channels (PPAs, partner repositories, etc.)
       in software-center.
       It contains a search entry and navigation buttons.
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS,
     PAGE_APP_PURCHASE) = range(3)

    def __init__(self, cache, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir,
                              show_ratings=False)
        self.channel = None
        self.apps_filter = None
        self.apps_search_term = ""
        self.current_appview_selection = None
        self.distro = get_distro()
        self.pane_name = _("Software Channels")
        # UI
        self._build_ui()

    def _build_ui(self):
        self.notebook.append_page(self.box_app_list, gtk.Label("channel"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))

    def _show_channel_overview(self):
        " helper that goes back to the overview page "
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
        
    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear()
        self.navigation_bar.remove_id(NAV_BUTTON_ID_SEARCH)

    def set_channel(self, channel):
        """
        set the current software channel object for display in the channel pane
        and set up the AppViewFilter if required
        """
        self.channel = channel
        # check to see if there is any section info that needs to be applied
        if channel._channel_color:
            self.section.set_color(channel._channel_color)
        if channel._channel_image_id:
            self.section.set_image_id(channel._channel_image_id)
        self.section_sync()

        # check if the channel needs to added
        if channel.needs_adding and channel._source_entry:
            dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL,
                                       type=gtk.MESSAGE_QUESTION)
            dialog.set_title("")
            dialog.set_markup("<big><b>%s</b></big>" % _("Add channel"))
            dialog.format_secondary_text(_("The selected channel is not yet "
                                           "added. Do you want to add it now?"))
            dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                               gtk.STOCK_ADD, gtk.RESPONSE_YES)
            res = dialog.run()
            dialog.destroy()
            if res == gtk.RESPONSE_YES:
                channel.needs_adding = False
                backend = get_install_backend()
                backend.add_sources_list_entry(channel._source_entry)
                backend.emit("channels-changed", True)
                backend.reload()
            return
        # normal operation
        self.nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE
        self.disable_show_hide_nonapps = False
        self.apps_filter = None
        if self.channel.installed_only:
            if self.apps_filter is None:
                self.apps_filter = AppViewFilter(self.db, self.cache)
            self.apps_filter.set_installed_only(True)
        # switch to applist, this will clear searches too
        self.display_list()
        
    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        LOG.debug("on_search_terms_changed: '%s'" % terms)
        self.apps_search_term = terms
        if not self.apps_search_term:
            self._clear_search()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
        
    def on_db_reopen(self, db):
        LOG.debug("got db-reopen signal")
        self.refresh_apps()
        self.app_details_view.refresh_app()

    def on_navigation_search(self, button, part):
        """ callback when the navigation button with id 'search' is clicked"""
        self.display_search()

    def on_navigation_list(self, button, part):
        """callback when the navigation button with id 'list' is clicked"""
        if not button.get_active():
            return
        self.display_list()
    
    def display_list(self):
        self._clear_search()
        self._show_channel_overview()
        # only emit something if the model is there
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))

    def on_navigation_details(self, button, part):
        """callback when the navigation button with id 'details' is clicked"""
        if not button.get_active():
            return
        self.display_details()
    
    def display_details(self):
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.searchentry.hide()
        self.action_bar.clear()
        
    def on_navigation_purchase(self, button, part):
        """callback when the navigation button with id 'purchase' is clicked"""
        if not button.get_active():
            return
        self.display_purchase()
        
    def display_purchase(self):
        self.notebook.set_current_page(self.PAGE_APP_PURCHASE)
        self.searchentry.hide()
        self.action_bar.clear()
        
    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        LOG.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def display_search(self):
        self.navigation_bar.remove_id(NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APPLIST)
        model = self.app_view.get_model()
        if model:
            length = len(self.app_view.get_model())
            self.emit("app-list-changed", length)
        self.searchentry.show()
    
    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        # no status text in the details page
        if self.notebook.get_current_page() == self.PAGE_APP_DETAILS:
            return ""
        # otherwise, show status based on search or not
        model = self.app_view.get_model()
        if not model:
            return ""
        length = len(self.app_view.get_model())
        if self.channel.installed_only:
            if len(self.searchentry.get_text()) > 0:
                return gettext.ngettext("%(amount)s matching item",
                                        "%(amount)s matching items",
                                        length) % { 'amount' : length, }
            else:
                return gettext.ngettext("%(amount)s item installed",
                                        "%(amount)s items installed",
                                        length) % { 'amount' : length, }
        else:
            if len(self.searchentry.get_text()) > 0:
                return gettext.ngettext("%(amount)s matching item",
                                        "%(amount)s matching items",
                                        length) % { 'amount' : length, }
            else:
                return gettext.ngettext("%(amount)s item available",
                                        "%(amount)s items available",
                                        length) % { 'amount' : length, }
                                    
    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the channel pane
        return False
        
    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return self.notebook.get_current_page() == self.PAGE_APPLIST

if __name__ == "__main__":
    #logging.basicConfig(level=logging.DEBUG)
    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    db = xapian.Database(pathname)
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")
    cache = apt.Cache(apt.progress.text.OpProgress())
    cache.ready = True

    w = ChannelPane(cache, db, icons, datadir)
    w.show()

    win = gtk.Window()
    win.add(w)
    win.set_size_request(400, 600)
    win.show_all()

    gtk.main()

