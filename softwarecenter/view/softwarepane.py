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

from gettext import gettext as _

from widgets.mkit import floats_from_gdkcolor, floats_from_string
from widgets.pathbar_gtk_atk import NavigationBar
from widgets.searchentry import SearchEntry
from widgets.actionbar import ActionBar
from widgets.spinner import Spinner

from softwarecenter.backend import get_install_backend
from softwarecenter.view.basepane import BasePane

from appview import AppView, AppStore

if "SOFTWARE_CENTER_APPDETAILS_WEBKIT" in os.environ:
    from appdetailsview_webkit import AppDetailsViewWebkit as AppDetailsView
else:
    from  appdetailsview_gtk import AppDetailsViewGtk as AppDetailsView

from softwarecenter.db.database import Application

LOG = logging.getLogger(__name__)

def wait_for_apt_cache_ready(f):
    """ decorator that ensures that the cache is ready using a
        gtk idle_add - needs a cache as argument
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        # check if the cache is ready and 
        if not self.cache.ready:
            if self.app_view.window:
                self.app_view.window.set_cursor(self.busy_cursor)
            glib.timeout_add(500, lambda: wrapper(*args, **kwargs))
            return False
        # cache ready now
        if self.app_view.window:
            self.app_view.window.set_cursor(None)
        f(*args, **kwargs)
        return False
    return wrapper


MASK_SURFACE_CACHE = {}


class SoftwareSection(object):

    def __init__(self):
        self._image_id = 0
        self._section_icon = None
        self._section_color = None
        return

    def render(self, cr, a):
        # sky
        r,g,b = self._section_color
        lin = cairo.LinearGradient(0,a.y,0,a.y+150)
        lin.add_color_stop_rgba(0, r,g,b, 0.3)
        lin.add_color_stop_rgba(1, r,g,b,0)
        cr.set_source(lin)
        cr.rectangle(0,0,
                     a.width, 150)
        cr.fill()

        # clouds
        s = MASK_SURFACE_CACHE[self._image_id]
        cr.set_source_surface(s, a.width-s.get_width(), 0)
        cr.paint()
        return

    def set_icon(self, icon):
        self._section_icon = icon
        return

    def set_image(self, id, path):
        image = cairo.ImageSurface.create_from_png(path)
        self._image_id = id
        global MASK_SURFACE_CACHE
        MASK_SURFACE_CACHE[id] = image
        return

    def set_image_id(self, id):
        self._image_id = id
        return

    def set_color(self, color_spec):
        color = floats_from_string(color_spec)
        self._section_color = color
        return

    def get_image(self):
        return MASK_SURFACE_CACHE[self._image_id]


class SoftwarePane(gtk.VBox, BasePane):
    """ Common base class for InstalledPane and AvailablePane """

    __gsignals__ = {
        "app-list-changed" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (int, ),
                             ),
    }
    PADDING = 6
    
    (PAGE_APPVIEW,
     PAGE_SPINNER) = range(2)

    def __init__(self, cache, history, db, distro, icons, datadir, show_ratings=False):
        gtk.VBox.__init__(self)
        BasePane.__init__(self)
        # other classes we need
        self.cache = cache
        self.history = history
        self.db = db
        self.distro = distro
        self.db.connect("reopen", self.on_db_reopen)
        self.icons = icons
        self.datadir = datadir
        self.backend = get_install_backend()
        self.nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE
        self.disable_show_hide_nonapps = False
        # refreshes can happen out-of-bound so we need to be sure
        # that we only set the new model (when its available) if
        # the refresh_seq_nr of the ready model matches that of the
        # request (e.g. people click on ubuntu channel, get impatient, click
        # on partner channel)
        self.refresh_seq_nr = 0
        # common UI elements (applist and appdetails) 
        # its the job of the Child class to put it into a good location
        # list
        self.app_view = AppView(show_ratings)
        self.app_view.connect("application-selected", 
                              self.on_application_selected)
        self.scroll_app_list = gtk.ScrolledWindow()
        self.scroll_app_list.set_policy(gtk.POLICY_AUTOMATIC, 
                                        gtk.POLICY_AUTOMATIC)
                             
        # make a spinner to display while the applist is loading
        self.spinner = Spinner()        
        self.spinner.set_size_request(48, 48)
        
        # use a table for the spinner (otherwise the spinner is massive!)
        self.spinner_table = gtk.Table(3, 3, False)
        self.spinner_table.attach(self.spinner, 1, 2, 1, 2, gtk.EXPAND, gtk.EXPAND)
        
        self.spinner_view = gtk.Viewport()
        self.spinner_view.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(1.0, 1.0, 1.0))
        self.spinner_view.add(self.spinner_table)
        self.spinner_view.set_shadow_type(gtk.SHADOW_NONE)
        self.scroll_app_list.add(self.app_view)
                
        self.app_view.connect("application-activated", 
                              self.on_application_activated)
        # details
        self.scroll_details = gtk.ScrolledWindow()
        self.scroll_details.set_policy(gtk.POLICY_AUTOMATIC, 
                                        gtk.POLICY_AUTOMATIC)
        self.app_details = AppDetailsView(self.db, 
                                          self.distro,
                                          self.icons, 
                                          self.cache, 
                                          self.history,
                                          self.datadir)
        self.scroll_details.add(self.app_details)
        # cursor
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)
        # when the cache changes, refresh the app list
        self.cache.connect("cache-ready", self.on_cache_ready)
        # COMMON UI elements
        # navigation bar and search on top in a hbox
        self.navigation_bar = NavigationBar()
        self.searchentry = SearchEntry()
        self.searchentry.connect("terms-changed", self.on_search_terms_changed)
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
                                       "details")
        self.notebook.set_current_page(self.PAGE_APP_DETAILS)
        self.app_details.show_app(app)

    def update_app_view(self):
        """
        Update the app_view.  If no row is selected, then the previously
        selected app is reselected if it is found in the model, else the
        first app in the list is selected.  If a row is already selected,
        nothing is done.
        """
        model = self.app_view.get_model()
        current_app = self.get_current_app()
        
        if model and current_app in model.app_index_map:
            index =  model.app_index_map.get(current_app)
            LOG.debug("found app: %s at index %s" % (current_app.pkgname, index))
            self.app_view.set_cursor(index)
            
    def show_appview_spinner(self):
        """ display the spinner in the appview panel """
        self.action_bar.clear()
        self.spinner.hide()
        self.spinner_notebook.set_current_page(self.PAGE_SPINNER)
        # "mask" the spinner momentarily to prevent it from flashing into
        # view in the case of short delays where it isn't actually needed
        gobject.timeout_add(100, self._unmask_appview_spinner)
        
    def _unmask_appview_spinner(self):
        self.spinner.start()
        self.spinner.show()
        
    def hide_appview_spinner(self):
        """ hide the spinner and display the appview in the panel """
        self.spinner.stop()
        self.spinner_notebook.set_current_page(self.PAGE_APPVIEW)

    def set_section(self, section):
        self.section = section
        self.app_details.set_section(section)
        return

    def section_sync(self):
        self.app_details.set_section(self.section)
        return
        
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
            if appstore.nonapps_visible == AppStore.NONAPPS_ALWAYS_VISIBLE:
                pkgs = appstore.nonapp_pkgs
                apps = len(appstore) - pkgs
            else:
                if showing_installed:
                    # estimate by using the installed apps count when generating
                    # the pkgs value
                    # FIXME:  for smaller appstores, we should be able to count the
                    #         number of installed non-apps for an accurate count
                    apps = len(appstore)
                    pkgs = min(self.cache.installed_count, appstore.nonapp_pkgs) - apps
                else:
                    apps = len(appstore)
                    if appstore.limit and appstore.limit < appstore.nonapp_pkgs:
                        pkgs = appstore.limit - apps
                    else:
                        pkgs = appstore.nonapp_pkgs - apps

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
                label = gettext.ngettext("_Hide %i technical item_",
                                         "_Hide %i technical items_",
                                         pkgs) % pkgs
                self.action_bar.set_label(label, self._hide_nonapp_pkgs) 
            else:
                label = gettext.ngettext("_Show %i technical item_",
                                         "_Show %i technical items_",
                                         pkgs) % pkgs
                self.action_bar.set_label(label, self._show_nonapp_pkgs)
            
    def _show_nonapp_pkgs(self):
        self.nonapps_visible = AppStore.NONAPPS_ALWAYS_VISIBLE
        self.refresh_apps()

    def _hide_nonapp_pkgs(self):
        self.nonapps_visible = AppStore.NONAPPS_MAYBE_VISIBLE
        self.refresh_apps()

    def get_status_text(self):
        """return user readable status text suitable for a status bar"""
        raise NotImplementedError
        
    @wait_for_apt_cache_ready
    def refresh_apps(self):
        " stub implementation "
        pass
    
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

