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
import bisect
import glib
import gobject
import gtk
import logging
import os
import xapian
import cairo
import gettext
import dialogs

from gettext import gettext as _

from widgets.mkit import floats_from_gdkcolor, floats_from_string
from widgets.pathbar_gtk_atk import NavigationBar
from widgets.searchentry import SearchEntry
from widgets.actionbar import ActionBar
from widgets.spinner import SpinnerView

from softwarecenter.backend import get_install_backend
from softwarecenter.enums import *
from softwarecenter.view.basepane import BasePane
from softwarecenter.utils import wait_for_apt_cache_ready, ExecutionTime

from appview import AppView, AppStore
from purchaseview import PurchaseView

if "SOFTWARE_CENTER_APPDETAILS_WEBKIT" in os.environ:
    from appdetailsview_webkit import AppDetailsViewWebkit as AppDetailsView
else:
    from  appdetailsview_gtk import AppDetailsViewGtk as AppDetailsView

from softwarecenter.db.database import Application

LOG = logging.getLogger(__name__)



class SoftwareSection(object):
    
    MASK_SURFACE_CACHE = {}

    def __init__(self):
        self._image_id = 0
        self._section_icon = None
        self._section_color = None
        return

    def render(self, cr, a):
        # sky
        r,g,b = self._section_color
        lin = cairo.LinearGradient(a.x,a.y,a.x,a.y+200)
        lin.add_color_stop_rgba(0, r,g,b, 0.3)
        lin.add_color_stop_rgba(1, r,g,b,0)
        cr.set_source(lin)
        cr.rectangle(a.x,a.y,
                     a.width, 200)
        cr.fill()

        # clouds
        s = self.MASK_SURFACE_CACHE[self._image_id]
        cr.set_source_surface(s, a.width-s.get_width(), 0)
        cr.paint()
        return

    def set_icon(self, icon):
        self._section_icon = icon
        return

    def set_image(self, id, path):
        image = cairo.ImageSurface.create_from_png(path)
        self._image_id = id
        self.MASK_SURFACE_CACHE[id] = image
        return

    def set_image_id(self, id):
        self._image_id = id
        return

    def set_color(self, color_spec):
        color = floats_from_string(color_spec)
        self._section_color = color
        return

    def get_image(self):
        return self.MASK_SURFACE_CACHE[self._image_id]


class SoftwarePane(gtk.VBox, BasePane):
    """ Common base class for InstalledPane, AvailablePane and ChannelPane"""

    __gsignals__ = {
        "app-list-changed" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (int, ),
                             ),
    }
    PADDING = 6
    
    # pages for the spinner notebook
    (PAGE_APPVIEW,
     PAGE_SPINNER) = range(2)

    def __init__(self, cache, db, distro, icons, datadir, show_ratings=False):
        gtk.VBox.__init__(self)
        BasePane.__init__(self)
        # other classes we need
        self.cache = cache
        self.db = db
        self.distro = distro
        self.icons = icons
        self.datadir = datadir
        self.show_ratings = show_ratings
        self.backend = get_install_backend()
        self.nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE
        self.disable_show_hide_nonapps = False
        # refreshes can happen out-of-bound so we need to be sure
        # that we only set the new model (when its available) if
        # the refresh_seq_nr of the ready model matches that of the
        # request (e.g. people click on ubuntu channel, get impatient, click
        # on partner channel)
        self.refresh_seq_nr = 0
        # data for the refresh_apps()
        self.channel = None
        self.apps_category = None
        self.apps_subcategory = None
        self.apps_search_term = None
        self.custom_list_mode = False
        # Create the basic frame for the common view
        # navigation bar and search on top in a hbox
        self.navigation_bar = NavigationBar()
        self.searchentry = SearchEntry()
        self.top_hbox = gtk.HBox(spacing=self.PADDING)
        self.top_hbox.set_border_width(self.PADDING)
        self.top_hbox.pack_start(self.navigation_bar)
        self.top_hbox.pack_start(self.searchentry, expand=False)
        self.pack_start(self.top_hbox, expand=False)
        #self.pack_start(gtk.HSeparator(), expand=False)
        # a notebook below
        self.notebook = gtk.Notebook()
        self.notebook.set_show_tabs(False)
        self.notebook.set_show_border(False)
        
        # make a spinner view to display while the applist is loading
        self.spinner_view = SpinnerView()
        self.spinner_notebook = gtk.Notebook()
        self.spinner_notebook.set_show_tabs(False)
        self.spinner_notebook.set_show_border(False)
        self.spinner_notebook.append_page(self.notebook)
        self.spinner_notebook.append_page(self.spinner_view)
        
        self.pack_start(self.spinner_notebook)
        # a bar at the bottom (hidden by default) for contextual actions
        self.action_bar = ActionBar()
        self.pack_start(self.action_bar, expand=False)
        self.top_hbox.connect('expose-event', self._on_expose)
        
        # cursor
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
        
    def init_view(self):
        """
        Initialize those UI components that are common to all subclasses of
        SoftwarePane.  Note that this method is intended to be called by
        the subclass itself at the start of its own init_view() implementation.
        """
        # common UI elements (applist and appdetails) 
        # its the job of the Child class to put it into a good location
        # list
        self.label_app_list_header = gtk.Label()
        self.label_app_list_header.set_alignment(0.1, 0.5)
        self.label_app_list_header.connect(
            "activate-link", self._on_label_app_list_header_activate_link)
        self.box_app_list = gtk.VBox()
        self.box_app_list.pack_start(
            self.label_app_list_header, expand=False, fill=False, padding=12)
        self.app_view = AppView(self.show_ratings)
        self.scroll_app_list = gtk.ScrolledWindow()
        self.scroll_app_list.set_policy(gtk.POLICY_AUTOMATIC, 
                                        gtk.POLICY_AUTOMATIC)
        self.scroll_app_list.add(self.app_view)
        self.box_app_list.pack_start(self.scroll_app_list)
        self.app_view.connect("application-selected", 
                              self.on_application_selected)
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
                                             
        # details
        self.scroll_details = gtk.ScrolledWindow()
        self.scroll_details.set_policy(gtk.POLICY_AUTOMATIC, 
                                        gtk.POLICY_AUTOMATIC)
        self.app_details_view = AppDetailsView(self.db, 
                                               self.distro,
                                               self.icons, 
                                               self.cache, 
                                               self.datadir)
        self.app_details_view.connect("purchase-requested",
                                      self.on_purchase_requested)
        self.scroll_details.add(self.app_details_view)
        # purchase view
        self.purchase_view = PurchaseView()
        self.purchase_view.connect("purchase-succeeded", self.on_purchase_succeeded)
        self.purchase_view.connect("purchase-failed", self.on_purchase_failed)
        self.purchase_view.connect("purchase-cancelled-by-user", self.on_purchase_cancelled_by_user)
        # when the cache changes, refresh the app list
        self.cache.connect("cache-ready", self.on_cache_ready)
        
        # connect signals
        self.searchentry.connect("terms-changed", self.on_search_terms_changed)
        self.connect("app-list-changed", self.on_app_list_changed)
        
        # db reopen
        self.db.connect("reopen", self.on_db_reopen)

    def _on_expose(self, widget, event):
        """ Draw a horizontal line that separates the top hbox from the page content """
        a = widget.allocation
        self.style.paint_shadow(widget.window, self.state,
                                gtk.SHADOW_IN,
                                (a.x, a.y+a.height-1, a.width, 1),
                                widget, "viewport",
                                a.x, a.y+a.height-1,
                                a.width, a.y+a.height-1)
        return

    def on_cache_ready(self, cache):
        " refresh the application list when the cache is re-opened "
        LOG.debug("on_cache_ready")
        # it only makes sense to refresh if there is something to
        # refresh, otherwise we create a bunch of (not yet needed)
        # AppStore objects on startup when the cache sends its 
        # initial "cache-ready" signal
        model = self.app_view.get_model()
        if model is None:
            return
        # FIXME: preserve selection too
        # get previous vadjustment and reapply it
        vadj = self.scroll_app_list.get_vadjustment()
        self.refresh_apps()
        # needed otherwise we jump back to the beginning of the table
        if vadj:
            vadj.value_changed()

    def on_application_activated(self, appview, app):
        """callback when an app is clicked"""
        LOG.debug("on_application_activated: '%s'" % app)
        details = app.get_details(self.db)
        self.navigation_bar.add_with_id(details.display_name,
                                       self.on_navigation_details,
                                       NAV_BUTTON_ID_DETAILS)
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.app_details_view.show_app(app)
        
    def on_purchase_requested(self, widget, app, url):
        self.navigation_bar.add_with_id(_("Buy"),
                                       self.on_navigation_purchase,
                                       NAV_BUTTON_ID_PURCHASE)
        self.appdetails = app.get_details(self.db)
        iconname = self.appdetails.icon
        self.purchase_view.initiate_purchase(app, iconname, url)
        
    def on_purchase_succeeded(self, widget):
        # switch to the details page to display the transaction is in progress
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.navigation_bar.remove_id(NAV_BUTTON_ID_PURCHASE)
        
    def on_purchase_failed(self, widget):
        # return to the the appdetails view via the button to reset it
        self._click_appdetails_view()
        dialogs.error(None,
                      _("Failure in the purchase process."),
                      _("Sorry, something went wrong. Your payment "
                        "has been cancelled."))
        
    def on_purchase_cancelled_by_user(self, widget):
        # return to the the appdetails view via the button to reset it
        self._click_appdetails_view()
            
    def _click_appdetails_view(self):
        details_button = self.navigation_bar.get_button_from_id(NAV_BUTTON_ID_DETAILS)
        if details_button:
            self.navigation_bar.set_active(details_button)
                                       
    def show_appview_spinner(self):
        """ display the spinner in the appview panel """
        self.action_bar.clear()
        self.spinner_view.stop()
        self.spinner_notebook.set_current_page(self.PAGE_SPINNER)
        # "mask" the spinner view momentarily to prevent it from flashing into
        # view in the case of short delays where it isn't actually needed
        gobject.timeout_add(100, self._unmask_appview_spinner)
        
    def _unmask_appview_spinner(self):
        self.spinner_view.start()
        
    def hide_appview_spinner(self):
        """ hide the spinner and display the appview in the panel """
        self.spinner_view.stop()
        self.spinner_notebook.set_current_page(self.PAGE_APPVIEW)

    def set_section(self, section):
        self.section = section
        self.app_details_view.set_section(section)
        return

    def section_sync(self):
        self.app_details_view.set_section(self.section)
        return

    def on_app_list_changed(self, pane, length):
        """internal helper that keeps the the action bar up-to-date by
           keeping track of the app-list-changed signals
        """
        self.update_show_hide_nonapps()
        self.update_search_help()
        
    def update_show_hide_nonapps(self):
        """
        update the state of the show/hide non-applications control
        in the action_bar
        """
        appstore = self.app_view.get_model()
        if not appstore:
            self.action_bar.unset_label()
            return
        
        # first figure out if we are only showing installed
        if appstore.filter:
            showing_installed = appstore.filter.installed_only
        else:
            showing_installed = False

        # calculate the number of apps/pkgs
        pkgs = 0
        apps = 0
        if appstore.active:
            if appstore.limit > 0 and appstore.limit < appstore.nr_pkgs:
                apps = min(appstore.limit, appstore.nr_apps)
                pkgs = min(appstore.limit - apps, appstore.nr_pkgs)
            else:
                apps = appstore.nr_apps
                pkgs = appstore.nr_pkgs

        self.action_bar.unset_label()
        
        if (appstore and 
            appstore.active and
            self.is_applist_view_showing() and
            pkgs > 0 and 
            apps > 0 and
            not self.disable_show_hide_nonapps):
            if appstore.nonapps_visible == AppStore.NONAPPS_ALWAYS_VISIBLE:
                # TRANSLATORS: the text inbetween the underscores acts as a link
                # In most/all languages you will want the whole string as a link
                label = gettext.ngettext("_Hide %(amount)i technical item_",
                                         "_Hide %(amount)i technical items_",
                                         pkgs) % { 'amount': pkgs, }
                self.action_bar.set_label(label, self._hide_nonapp_pkgs) 
            else:
                label = gettext.ngettext("_Show %(amount)i technical item_",
                                         "_Show %(amount)i technical items_",
                                         pkgs) % { 'amount': pkgs, }
                self.action_bar.set_label(label, self._show_nonapp_pkgs)

    def update_search_help(self):
        search = self.searchentry.get_text()
        appstore = self.app_view.get_model()
        if (search and appstore is not None and len(appstore) == 0):
            category = self.get_current_category()
            correction = self.db.get_spelling_correction(search)
            if category:
                text = _("Search term not found in current category, "
                         "do you want to search "
                         "<a href=\"search-all:\">all categories</a> instead ?")
                self.label_app_list_header.set_markup(text)
                self.label_app_list_header.set_visible(True)
                return
            elif correction:
                ref = "<a href=\"search:%s\">%s</a>" % (correction, correction)
                text = _("Search term not found, did you mean: %s ?") % ref
                self.label_app_list_header.set_markup(text)
                self.label_app_list_header.set_visible(True)
                return
        # catchall, hide if we don't have anything useful to suggest
        self.label_app_list_header.set_visible(False)
            
    def _on_label_app_list_header_activate_link(self, link, uri):
        #print "actiavte: ", link, uri
        if uri.startswith("search:"):
            self.searchentry.set_text(uri[len("search:"):])
        elif uri.startswith("search-all:"):
            self.unset_current_category()
            self.refresh_apps()
        # FIXME: add ability to remove categories restriction here
        # True stops event propergation
        return True

    def _show_nonapp_pkgs(self):
        self.nonapps_visible = AppStore.NONAPPS_ALWAYS_VISIBLE
        self.refresh_apps()

    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE
        self.refresh_apps()

    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        raise NotImplementedError

    def get_query(self):
        channel_query = None
        name = self.pane_name
        if self.channel:
            channel_query = self.channel.query
            name = self.channel.display_name
        # search terms
        if self.apps_search_term:
            query = self.db.get_query_list_from_search_entry(
                self.apps_search_term, channel_query)
            self.navigation_bar.add_with_id(_("Search Results"),
                                              self.on_navigation_search, 
                                              NAV_BUTTON_ID_SEARCH,
                                              do_callback=False)
            return query
        # overview list
        self.navigation_bar.add_with_id(name,
                                        self.on_navigation_list,
                                        NAV_BUTTON_ID_LIST,
                                        do_callback=False)
        # if we are in a channel, limit to that
        if channel_query:
            return channel_query
        # ... otherwise show all
        return xapian.Query("")
        
    def refresh_apps(self, query=None):
        """refresh the applist and update the navigation bar """
        LOG.debug("refresh_apps")

        # FIXME: make this available for all panes
        if query is None:
            query = self.get_query()
        old_model = self.app_view.get_model()
        # exactly the same model, nothing to do
        if (old_model and 
            query == old_model.search_query and
            self.apps_filter == old_model.filter and
            self.nonapps_visible == old_model.nonapps_visible):
            # emit the signal to ensure that the ui updates status bar
            # and all (name is misleading :/
            self.emit("app-list-changed", len(self.app_view.get_model()))
            return

        self.show_appview_spinner()
        self._refresh_apps_with_apt_cache(query)

    @wait_for_apt_cache_ready
    def _refresh_apps_with_apt_cache(self, query):
        self.refresh_seq_nr += 1
        LOG.debug("softwarepane query: %s" % query)

        old_model = self.app_view.get_model()
        if old_model is not None:
            # *ugh* deactivate the old model because otherwise it keeps
            # getting progress_changed events and eats CPU time until its
            # garbage collected
            old_model.active = False
            while gtk.events_pending():
                gtk.main_iteration()

        LOG.debug("softwarepane query: %s" % query)
        # create new model and attach it
        seq_nr = self.refresh_seq_nr
        # special case to disable show/hide nonapps for the "Featured" category
        # we do the same for the "System" category (LP: #636854)
        if (self.apps_category and 
            # FIXME: this should be a property of the category, not
            #        something we hardcode here
           (self.apps_category.untranslated_name == "Featured" or
            self.apps_category.untranslated_name == "System")):
            self.nonapps_visible = AppStore.NONAPPS_ALWAYS_VISIBLE
            self.disable_show_hide_nonapps = True
        else:
            self.disable_show_hide_nonapps = False
        # In custom list mode, search should yield the exact package name.
        new_model = AppStore(self.cache,
                             self.db,
                             self.icons,
                             query,
                             limit=self.get_app_items_limit(),
                             sortmode=self.get_sort_mode(),
                             exact=self.custom_list_mode,
                             nonapps_visible = self.nonapps_visible,
                             filter=self.apps_filter)
        #print "new_model", new_model, len(new_model), seq_nr
        # between request of the new model and actual delivery other
        # events may have happend
        if seq_nr != self.refresh_seq_nr:
            LOG.info("discarding new model (%s != %s)" % (seq_nr, self.refresh_seq_nr))
            return False

        # set model
        self.app_view.set_model(new_model)
        self.app_view.get_model().active = True

        self.hide_appview_spinner()
        # we can not use "new_model" here, because set_model may actually
        # discard new_model and just update the previous one
        self.emit("app-list-changed", len(self.app_view.get_model()))
        return False

    def get_app_items_limit(self):
        " stub implementation "
        return 0

    def get_sort_mode(self):
        if self.apps_search_term:
            return SORT_BY_SEARCH_RANKING
        elif self.apps_category:
            return self.apps_category.sortmode
        return SORT_BY_ALPHABET

    def on_search_terms_changed(self, terms):
        " stub implementation "
        pass

    def on_db_reopen(self):
        " stub implementation "
        pass

    def is_category_view_showing(self):
        " stub implementation "
        pass
        
    def is_applist_view_showing(self):
        " stub implementation "
        
    def get_current_app(self):
        " stub implementation "
        pass

    def on_application_selected(self, widget, app):
        " stub implementation "
        pass

    def get_current_category(self):
        " stub implementation "
        pass

    def unset_current_category(self):
        " stub implementation "
        pass
