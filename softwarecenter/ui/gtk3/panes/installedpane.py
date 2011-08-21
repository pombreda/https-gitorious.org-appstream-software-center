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

from gi.repository import Gtk
import logging
import xapian
from gi.repository import GObject

from gettext import gettext as _

from softwarecenter.enums import (NonAppVisibility,
                                  SortMethods)
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.db.categories import (CategoriesParser,
                                          categories_sorted_by_name)
from softwarecenter.ui.gtk3.models.appstore2 import (
    AppTreeStore, CategoryRowReference, UncategorisedRowRef)
from softwarepane import SoftwarePane
from softwarecenter.db.appfilter import AppFilter

LOG=logging.getLogger(__name__)

def interrupt_build_and_wait(f):
    """ decorator that ensures that a build of the categorised installed apps
        is interrupted before a new build commences.
        expects self._build_in_progress and self._halt_build as properties
    """
    def wrapper(*args, **kwargs):
        self = args[0]
        if self._build_in_progress:
            LOG.debug('Waiting for build to exit...')
            self._halt_build = True
            GObject.timeout_add(200, lambda: wrapper(*args, **kwargs))
            return False
        # ready now
        self._halt_build = False
        f(*args, **kwargs)
        return False
    return wrapper


class InstalledPane(SoftwarePane, CategoriesParser):
    """Widget that represents the installed panel in software-center
       It contains a search entry and navigation buttons
    """

    class Pages:
        # page names, useful for debuggin
        NAMES = ('list', 'details')
        # the actual page id's
        (LIST,
         DETAILS) = range(2)
        # the default page
        HOME = LIST

    __gsignals__ = {'installed-pane-created':(GObject.SignalFlags.RUN_FIRST,
                                              None,
                                              ())}

    def __init__(self, cache, db, distro, icons, datadir):

        # parent
        SoftwarePane.__init__(self, cache, db, distro, icons, datadir, show_ratings=False)
        CategoriesParser.__init__(self, db)

        self.current_appview_selection = None
        self.loaded = False
        self.pane_name = _("Installed Software")

        self.installed_apps = 0

        # switches to terminate build in progress
        self._build_in_progress = False
        self._halt_build = False

        self.nonapps_visible = NonAppVisibility.NEVER_VISIBLE

    def init_view(self):
        if self.view_initialized: return

        SoftwarePane.init_view(self)

        self.search_aid.set_no_show_all(True)
        self.notebook.append_page(self.box_app_list, Gtk.Label(label="installed"))

        # details
        self.notebook.append_page(self.scroll_details, Gtk.Label(label="details"))
        # initial refresh
        self.state.search_term = ""

        # build models and filters
        self.base_model = AppTreeStore(self.db, self.cache, self.icons)

        self.treefilter = self.base_model.filter_new(None)
        self.treefilter.set_visible_func(self._row_visibility_func,
                                         AppTreeStore.COL_ROW_DATA)
        self.app_view.set_model(self.treefilter)
        self.app_view.tree_view.connect("row-collapsed", self._on_row_collapsed)

        self.visible_docids = None

        self._all_cats = self.parse_applications_menu('/usr/share/app-install')
        self._all_cats = categories_sorted_by_name(self._all_cats)

        # now we are initialized
        self.emit("installed-pane-created")
        self.show_all()

        # hacky, hide the header
        self.app_view.header_hbox.hide()

        self.view_initialized = True
        return False

    def _on_row_collapsed(self, view, it, path):
        return

    def _row_visibility_func(self, model, it, col):
        row = model.get_value(it, col)
        if self.visible_docids is None:
            if isinstance(row, CategoryRowReference):
                row.vis_count = row.pkg_count
            return True

        elif isinstance(row, CategoryRowReference):
            return row.untranslated_name in self.visible_cats.keys()

        elif row is None: return False

        return row.get_docid() in self.visible_docids

    def _use_category(self, cat):
        # System cat is large and slow to search, filter it in default mode

        if ('carousel-only' in cat.flags or 
            ((self.nonapps_visible == NonAppVisibility.NEVER_VISIBLE)
            and cat.untranslated_name == 'System')): return False

        return True

    def _hide_nonapp_pkgs(self):
        print 'hide nonapp'
        self.nonapps_visible = NonAppVisibility.NEVER_VISIBLE
        self.refresh_apps()

    #~ @interrupt_build_and_wait
    def _build_categorised_view(self):
        LOG.debug('Rebuilding categorised installedview...')
        self.cat_docid_map = {}
        enq = self.enquirer
        model = self.base_model # base model not treefilter
        model.clear()

        i = 0

        xfilter = AppFilter(self.db, self.cache)
        xfilter.set_installed_only(True)
        for cat in self._all_cats:
            # for each category do category query and append as a new
            # node to tree_view
            if not self._use_category(cat): continue
            query = self.get_query_for_cat(cat)
            LOG.debug("filter.instaleld_only: %s" % xfilter.installed_only)
            enq.set_query(query,
                          sortmode=SortMethods.BY_ALPHABET,
                          nonapps_visible=self.nonapps_visible,
                          filter=xfilter,
                          nonblocking_load=False,
                          persistent_duplicate_filter=(i>0))

            L = len(self.enquirer.matches)
            if L:
                i += L
                docs = enq.get_documents()
                self.cat_docid_map[cat.untranslated_name] = \
                                    set([doc.get_docid() for doc in docs])
                model.set_category_documents(cat, docs)

        # check for uncategorised pkgs
        enq.set_query(self.state.channel.query,
                      sortmode=SortMethods.BY_ALPHABET,
                      nonapps_visible=NonAppVisibility.MAYBE_VISIBLE,
                      filter=xfilter,
                      nonblocking_load=False,
                      persistent_duplicate_filter=(i>0))

        L = len(enq.matches)
        if L:
            # some foo for channels
            # if no categorised results but in channel, then use
            # the channel name for the category
            channel_name = None
            if not i and self.state.channel:
                channel_name = self.state.channel.display_name
            docs = enq.get_documents()
            tag = channel_name or 'Uncategorized'
            self.cat_docid_map[tag] = set([doc.get_docid() for doc in docs])
            model.set_nocategory_documents(docs, untranslated_name=tag,
                                           display_name=channel_name)
            i += L

        if i:
            self.app_view.tree_view.set_cursor(Gtk.TreePath(),
                                               None, False)
            if i <= 10:
                self.app_view.tree_view.expand_all()

        # cache the installed app count
        self.installed_count = i

        self.app_view._append_appcount(self.installed_count, installed=True)

        self.emit("app-list-changed", i)
        return

    def _check_expand(self):
        it = self.treefilter.get_iter_first()
        while it:
            path = self.treefilter.get_path(it)
            if self.state.search_term:# or path in self._user_expanded_paths:
                self.app_view.tree_view.expand_row(path, False)
            else:
                self.app_view.tree_view.collapse_row(path)

            it = self.treefilter.iter_next(it)
        return

    def _search(self, terms=None):
        if not terms:
            self.visible_docids = None
            self.state.search_term = ""
            self._clear_search()

        elif self.state.search_term != terms:
            self.state.search_term = terms
            xfilter = AppFilter(self.db, self.cache)
            xfilter.set_installed_only(True)
            self.enquirer.set_query(self.get_query(),
                                    nonapps_visible=self.nonapps_visible,
                                    filter=xfilter,
                                    nonblocking_load=True)

            self.visible_docids = self.enquirer.get_docids()
            self.visible_cats = self._get_vis_cats(self.visible_docids)

        self.treefilter.refilter()
        if terms:
            self.app_view.tree_view.expand_all()
        else:
            self._check_expand()
        return

    def get_query(self):
        # search terms
        return self.db.get_query_list_from_search_entry(
                                        self.state.search_term)

    def get_query_for_cat(self, cat):
        LOG.debug("self.state.channel: %s" % self.state.channel)
        if self.state.channel and self.state.channel.query:
            query = xapian.Query(xapian.Query.OP_AND,
                                 cat.query,
                                 self.state.channel.query)
            return query
        return cat.query

    @wait_for_apt_cache_ready
    def refresh_apps(self, *args, **kwargs):
        """refresh the applist and update the navigation bar """
        logging.debug("installedpane refresh_apps")
        self._build_categorised_view()
        return

    def _clear_search(self):
        # remove the details and clear the search
        self.searchentry.clear_with_no_signal()

    def on_search_terms_changed(self, searchentry, terms):
        """callback when the search entry widget changes"""
        logging.debug("on_search_terms_changed: '%s'" % terms)

        self._search(terms.strip())
        self.state.search_term = terms
        self.notebook.set_current_page(InstalledPane.Pages.LIST)
        return

    def _get_vis_cats(self, visids):
        vis_cats = {}
        appcount = 0
        visids = set(visids)
        for cat_uname, docids in self.cat_docid_map.iteritems():
            children = len(docids & visids)
            if children:
                appcount += children
                vis_cats[cat_uname] = children
        self.app_view._append_appcount(appcount, installed=True)
        return vis_cats

    def on_db_reopen(self, db):
        self.refresh_apps(rebuild=True)
        self.app_details_view.refresh_app()

    def on_application_selected(self, appview, app):
        """callback when an app is selected"""
        logging.debug("on_application_selected: '%s'" % app)
        self.current_appview_selection = app

    def get_callback_for_page(self, page, state):
        if page == InstalledPane.Pages.LIST:
            return self.display_overview_page
        return self.display_details_page

    def display_search(self):
        model = self.app_view.get_model()
        if model:
            self.emit("app-list-changed", len(model))
        self.searchentry.show()

    def display_overview_page(self, page, view_state):
        LOG.debug("view_state: %s" % view_state)
        self._build_categorised_view()

        if self.state.search_term:
            self._search(self.state.search_term)
        return True

    def get_current_app(self):
        """return the current active application object applicable
           to the context"""
        return self.current_appview_selection
        
    def is_category_view_showing(self):
        # there is no category view in the installed pane
        return False
        
    def is_applist_view_showing(self):
        """Return True if we are in the applist view """
        return (self.notebook.get_current_page() ==
                InstalledPane.Pages.LIST)
        
    def is_app_details_view_showing(self):
        """Return True if we are in the app_details view """
        return self.notebook.get_current_page() == InstalledPane.Pages.DETAILS


def get_test_window():
    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    # needed because available pane will try to get it
    vm = get_test_gtk3_viewmanager()
    vm # make pyflakes happy
    db = get_test_db()
    cache = get_test_pkg_info()
    datadir = get_test_datadir()
    icons = get_test_gtk3_icon_cache()

    w = InstalledPane(cache, db, 'Ubuntu', icons, datadir)
    w.show()

    win = Gtk.Window()
    win.set_data("pane", w)
    win.add(w)
    win.set_size_request(400, 600)
    win.connect("destroy", lambda x: Gtk.main_quit())

    # init the view
    w.init_view()

    from softwarecenter.backend.channel import AllInstalledChannel
    w.state.channel = AllInstalledChannel()
    w.display_overview_page(None, None)

    win.show_all()
    return win


if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()

