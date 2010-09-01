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

from appview import AppView, AppStore, AppViewFilter

from softwarepane import SoftwarePane, wait_for_apt_cache_ready

LOG = logging.getLogger(__name__)

class ChannelPane(SoftwarePane):
    """Widget that represents the channel pane for display of
       individual channels (PPAs, partner repositories, etc.)
       in software-center.
       It contains a search entry and navigation buttons.
    """

    (PAGE_APPLIST,
     PAGE_APP_DETAILS) = range(2)

    def __init__(self, cache, history, db, distro, icons, datadir):
        # parent
        SoftwarePane.__init__(self, cache, history, db, distro, icons, datadir,
                              show_ratings=False)
        self.channel = None
        self.apps_filter = None
        self.search_terms = ""
        self.current_appview_selection = None
        self.distro = get_distro()
        # UI
        self._build_ui()
        self.connect("app-list-changed", self._on_app_list_changed)
        self.nonapps_visible = False

    def _build_ui(self):
        self.notebook.append_page(self.scroll_app_list, gtk.Label("channel"))
        # details
        self.notebook.append_page(self.scroll_details, gtk.Label("details"))

    def _show_channel_overview(self):
        " helper that goes back to the overview page "
        self.navigation_bar.remove_id("details")
        self.notebook.set_current_page(self.PAGE_APPLIST)
        self.searchentry.show()
        
    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear()
        self.navigation_bar.remove_id("search")

    @wait_for_apt_cache_ready
    def refresh_apps(self):
        """refresh the applist after search changes and update the 
           navigation bar
        """
        LOG.debug("refresh_apps")
        if not self.channel:
            return
        self.refresh_seq_nr += 1
        channel_query = self.channel.get_channel_query()
        if self.search_terms:
            query = self.db.get_query_list_from_search_entry(self.search_terms,
                                                             channel_query)
            self.navigation_bar.add_with_id(_("Search Results"),
                                            self.on_navigation_search, 
                                            "search", do_callback=False)
        else:
            self.navigation_bar.add_with_id(
                self.channel.get_channel_display_name(),
                self.on_navigation_list,
                "list", do_callback=False)
            query = xapian.Query(channel_query)

        LOG.debug("channelpane query: %s" % query)
        # *ugh* deactivate the old model because otherwise it keeps
        # getting progress_changed events and eats CPU time until its
        # garbage collected
        old_model = self.app_view.get_model()
        
        # if the list is expected to contain many items, 
        #  clear the current model to display
        # an empty list while the full list is generated; 
        #  this prevents a visual glitch when
        # the list is replaced
        if ((self.channel.get_channel_name() == self.distro.get_distro_channel_name() and not 
             self.search_terms)):
            self.app_view.clear_model()
        
        if old_model is not None:
            old_model.active = False
            while gtk.events_pending():
                gtk.main_iteration()
        self._make_new_model(query, self.refresh_seq_nr)
        return False

    def _make_new_model(self, query, seq_nr):
        # something changed already
        if self.refresh_seq_nr != seq_nr:
            LOG.warn("early discarding new model (%s != %s)" % (seq_nr, self.refresh_seq_nr))
            return False
        # get a new store and attach it to the view
        if self.scroll_app_list.window:
            self.scroll_app_list.window.set_cursor(self.busy_cursor)
        # show all items for installed view channels
        if self.channel.installed_only:
            self.nonapps_visible = True
        new_model = AppStore(self.cache,
                             self.db, 
                             self.icons, 
                             query, 
                             limit=0,
                             sortmode=self.channel.get_channel_sort_mode(),
                             nonapps_visible = self.nonapps_visible,
                             filter=self.apps_filter)
        # between request of the new model and actual delivery other
        # events may have happend
        if self.scroll_app_list.window:
            self.scroll_app_list.window.set_cursor(None)
        if seq_nr == self.refresh_seq_nr:
            self.app_view.set_model(new_model)
            self.app_view.get_model().active = True
            # we can not use "new_model" here, because set_model may actually
            # discard new_model and just update the previous one
            self.emit("app-list-changed", len(self.app_view.get_model()))
        else:
            LOG.debug("discarding new model (%s != %s)" % (seq_nr, self.refresh_seq_nr))
        return False

    def set_channel(self, channel):
        """
        set the current software channel object for display in the channel pane
        and set up the AppViewFilter if required
        """
        self.channel = channel
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
        self.apps_filter = None
        if self.channel.only_packages_without_applications:
            self.apps_filter = AppViewFilter(self.db, self.cache)
            self.apps_filter.set_only_packages_without_applications(True)
        if self.channel.installed_only:
            if self.apps_filter is None:
                self.apps_filter = AppViewFilter(self.db, self.cache)
            self.apps_filter.set_installed_only(True)
        # switch to applist, this will clear searches too
        self.display_list()
        
    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        LOG.debug("on_search_terms_changed: '%s'" % terms)
        self.search_terms = terms
        if not self.search_terms:
            self._clear_search()
        self.refresh_apps()
        self.notebook.set_current_page(self.PAGE_APPLIST)
        
    def on_db_reopen(self, db):
        LOG.debug("got db-reopen signal")
        self.refresh_apps()
        self.app_details.refresh_app()

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
        
    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        LOG.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def _on_app_list_changed(self, pane, length):
        """internal helper that keeps the the action bar up-to-date by
           keeping track of the app-list-changed signals
        """
        self._update_action_bar()

    def _update_action_bar(self):
        appstore = self.app_view.get_model()

        # calculate the number of apps/pkgs
        # yes, this is 'strange', but we have to deal with the existing appstore
        if appstore and appstore.active:
            if appstore.nonapps_visible:
                pkgs = appstore.nonapp_pkgs
                apps = len(appstore) - pkgs
            else:
                apps = len(appstore)
                pkgs = appstore.nonapp_pkgs - apps
            #print 'apps: ' + str(apps)
            #print 'pkgs: ' + str(pkgs)

        self.action_bar.unset_label()

        if (appstore and appstore.active and not self.channel.installed_only and
            pkgs != apps and pkgs > 0 and apps > 0):
            if appstore.nonapps_visible:
                # TRANSLATORS: the text inbetween the underscores acts as a link
                # In most/all languages you will want the whole string as a link
                label = gettext.ngettext("_Hide %i technical item_",
                                         "_Hide %i technical items_",
                                         pkgs) % pkgs
                self.action_bar.set_label(label, self._hide_nonapp_pkgs) 
            elif not appstore.nonapps_visible:
                label = gettext.ngettext("_Show %i technical item_",
                                         "_Show %i technical items_",
                                         pkgs) % pkgs
                self.action_bar.set_label(label, self._show_nonapp_pkgs)

    def _show_nonapp_pkgs(self):
        self.nonapps_visible = True
        self.refresh_apps()

    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = False
        self.refresh_apps()

    def display_search(self):
        self.navigation_bar.remove_id("details")
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

