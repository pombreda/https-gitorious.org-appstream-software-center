# Copyright (C) 2009,2010 Canonical
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

#~ from __future__ import with_statement

from gi.repository import GObject
from gi.repository import Gtk, Gdk
import logging
import os
import xapian

from softwarecenter.enums import (AppActions, 
                                  NonAppVisibility,
                                  XapianValues,
                                  AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME,
                                  )

from softwarecenter.distro import get_distro
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.utils import ExecutionTime
from softwarecenter.backend import get_install_backend
from softwarecenter.netstatus import (get_network_watcher,
                                      network_state_is_connected)

from softwarecenter.ui.gtk3.em import em
from softwarecenter.ui.gtk3.models.appstore2 import AppGenericStore, CategoryRowReference

from softwarecenter.ui.gtk3.widgets.cellrenderers import (
                                   CellRendererAppView,
                                   CellButtonRenderer,
                                   CellButtonIDs)

from gettext import gettext as _


class AppView(Gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (GObject.SignalFlags.RUN_LAST,
                                        None,
                                        (GObject.TYPE_PYOBJECT,
                                         GObject.TYPE_PYOBJECT, 
                                         GObject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }

    VARIANT_INFO = 0
    VARIANT_REMOVE = 1
    VARIANT_INSTALL = 2

    def __init__(self, icons, show_ratings, store=None):
        Gtk.TreeView.__init__(self)
        self._logger = logging.getLogger("softwarecenter.view.appview")

        self.pressed = False
        self.focal_btn = None
        self._action_block_list = []
        self.expanded_path = None

        #~ # if this hacked mode is available everything will be fast
        #~ # and we can set fixed_height mode and still have growing rows
        #~ # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            self._logger.warn("ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # a11y: this is a cell renderer that only displays a icon, but still
        #       has a markup property for orca and friends
        # we use it so that orca and other a11y tools get proper text to read
        # it needs to be the first one, because that is what the tools look
        # at by default
        tr = CellRendererAppView(icons,
                                 show_ratings,
                                 "software-center-installed")
        tr.set_pixbuf_width(32)
        tr.set_button_spacing(em(0.3))

        # create buttons and set initial strings
        info = CellButtonRenderer(self,
                                  name=CellButtonIDs.INFO)
        info.set_markup_variants(
                    {self.VARIANT_INFO: _('More Info')})

        action = CellButtonRenderer(self,
                                    name=CellButtonIDs.ACTION)
        action.set_markup_variants(
                {self.VARIANT_INSTALL: _('Install'),
                 self.VARIANT_REMOVE: _('Remove')})

        tr.button_pack_start(info)
        tr.button_pack_end(action)

        column = Gtk.TreeViewColumn("Applications", tr,
                                    application=AppGenericStore.COL_ROW_DATA)
        column.set_cell_data_func(tr, self._cell_data_func_cb)
        column.set_fixed_width(200)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        self.append_column(column)

        # network status watcher
        watcher = get_network_watcher()
        watcher.connect("changed", self._on_net_state_changed, tr)

        # custom cursor
        self._cursor_hand = Gdk.Cursor.new(Gdk.CursorType.HAND2)

        self.connect("style-updated", self._on_style_updated, tr)
        # button and motion are "special"
        self.connect("button-press-event", self._on_button_press_event, tr)
        self.connect("button-release-event", self._on_button_release_event, tr)
        self.connect("key-press-event", self._on_key_press_event, tr)
        self.connect("key-release-event", self._on_key_release_event, tr)
        self.connect("motion-notify-event", self._on_motion, tr)
        self.connect("cursor-changed", self._on_cursor_changed, tr)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, tr)

        self.backend = get_install_backend()
        self._transactions_connected = False
        self.connect('realize', self._on_realize, tr)

    @property
    def appmodel(self):
        model = self.get_model()
        if isinstance(model, Gtk.TreeModelFilter):
            return model.get_model()
        return model
        
    def clear_model(self):
        vadjustment = self.get_scrolled_window_vadjustment()
        vadjustment.set_value(0)
        self.expanded_path = None
        self.appmodel.clear()

    def expand_path(self, path):
        if path is not None and not isinstance(path, Gtk.TreePath):
            raise TypeError, "Expects Gtk.TreePath or None, got %s" % type(path)

        model = self.get_model()
        old = self.expanded_path
        self.expanded_path = path

        if old is not None:
            model.row_changed(old, model.get_iter(old))
        if path == None: return

        model.row_changed(path, model.get_iter(path))
        return

#    def is_action_in_progress_for_selected_app(self):
#        """
#        return True if an install or remove of the current package
#        is in progress
#        """
#        (path, column) = self.get_cursor()
#        if path:
#            model = self.get_model()
#            return (model[path][AppGenericStore.COL_ROW_DATA].transaction_progress != -1)
#        return False

    def get_scrolled_window_vadjustment(self):
        scroll = self.get_parent()
        return scroll.get_vadjustment()

    def get_rowref(self, model, path):
        if path == None: return None
        return model[path][AppGenericStore.COL_ROW_DATA]

    def rowref_is_category(self, rowref):
        return isinstance(rowref, CategoryRowReference)

    def _on_realize(self, widget, tr):
        # connect to backend events once self is realized so handlers 
        # have access to the TreeView's initialised Gdk.Window
        if self._transactions_connected: return
        self.backend.connect("transaction-started", self._on_transaction_started, tr)
        self.backend.connect("transaction-finished", self._on_transaction_finished, tr)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped, tr)
        self._transactions_connected = True
        return

    def _calc_row_heights(self, tr):
        pad = em(0.3)
        tr.set_property('xpad', pad)
        tr.set_property('ypad', pad)

        for btn in tr.get_buttons():
            # recalc button geometry and cache
            btn.configure_geometry(self.create_pango_layout(""))

        btn_h = btn.height

        tr.normal_height = max(32 + 2*pad, em(2.5) + pad)
        tr.selected_height = tr.normal_height + btn_h + 3*pad
        return

    def _on_style_updated(self, widget, tr):
        self._calc_row_heights(tr)
        return

    def _on_motion(self, tree, event, tr):
        window = self.get_window()

        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y):
            window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path:
            window.set_cursor(None)
            return

        rowref = self.get_rowref(tree.get_model(), path[0])
        if not rowref: return

        if self.rowref_is_category(rowref):
            window.set_cursor(None)
            return

        use_hand = False
        for btn in tr.get_buttons():
            if btn.state == Gtk.StateType.INSENSITIVE:
                continue

            if btn.point_in(x, y):
                use_hand = True
                if self.focal_btn is btn:
                    btn.set_state(Gtk.StateFlags.ACTIVE)
                elif not self.pressed:
                    btn.set_state(Gtk.StateFlags.PRELIGHT)
            else:
                if btn.state != Gtk.StateFlags.NORMAL:
                    btn.set_state(Gtk.StateFlags.NORMAL)
        

        if use_hand:
            window.set_cursor(self._cursor_hand)
        else:
            window.set_cursor(None)
        return

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0]

        rowref = self.get_rowref(model, path)
        if not rowref: return

        if self.has_focus(): self.grab_focus()

        if self.rowref_is_category(rowref):
            self.expand_path(None)
            return

        sel.select_path(path)
        self._update_selected_row(view, tr, path)
        return

    def _update_selected_row(self, view, tr, path=None):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows: 
            return False

        row = rows[0]

        # update active app, use row-ref as argument
        self.expand_path(row)

        app = model[row][AppGenericStore.COL_ROW_DATA]

        action_btn = tr.get_button_by_name(
                            CellButtonIDs.ACTION)
        #if not action_btn: return False

        if not network_state_is_connected():
            action_btn.set_sensitive(False)
            return

        if self.appmodel.is_installed(app):
            action_btn.set_variant(self.VARIANT_REMOVE)
        else:
            action_btn.set_variant(self.VARIANT_INSTALL)
#~ 
        #~ if self.appmodel.get_transaction_progress(app) > 0:
            #~ action_btn.set_sensitive(False)
        #~ elif self.pressed and self.focal_btn == action_btn:
            #~ action_btn.set_state(Gtk.StateFlags.ACTIVE)
        #~ else:
            #~ action_btn.set_state(Gtk.StateFlags.NORMAL)

#        self.emit("application-selected", Application(name, pkgname, request))
        self.emit("application-selected", self.appmodel.get_application(app))
        return False

    def _on_row_activated(self, view, path, column, tr):
        rowref = self.get_rowref(view.get_model(), path)

        if not rowref: return

        if self.rowref_is_category(rowref): return

        x, y = self.get_pointer()
        for btn in tr.get_buttons():
            if btn.point_in(x, y): 
                return

        self.emit("application-activated", self.appmodel.get_application(rowref))
        return

    def _on_button_event_get_path(self, view, event):
        if event.button != 1: return False

        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res: return False

        # check the path is valid and is not a category row
        path = res[0]
        is_cat = self.rowref_is_category(self.get_rowref(view.get_model(), path))
        if path is None or is_cat: return False

        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path): return False

        return path

    def _on_button_press_event(self, view, event, tr):
        if not self._on_button_event_get_path(view, event): return

        self.pressed = True
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != Gtk.StateType.INSENSITIVE):
                self.focal_btn = btn
                btn.set_state(Gtk.StateFlags.ACTIVE)
                view.queue_draw()
                return
        self.focal_btn = None
        return

    def _on_button_release_event(self, view, event, tr):
        path = self._on_button_event_get_path(view, event)
        if not path: return

        self.pressed = False
        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != Gtk.StateFlags.INSENSITIVE):
                btn.set_state(Gtk.StateFlags.NORMAL)
                self.get_window().set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                view.queue_draw()
                break
        self.focal_btn = None
        return

    def _on_key_press_event(self, widget, event, tr):
        kv = event.keyval
        #print kv
        r = False
        if kv == Gdk.KEY_Right: # right-key
            btn = tr.get_button_by_name('action0')
            if btn.state != Gtk.StateType.INSENSITIVE:
                btn.has_focus = True
                btn = tr.get_button_by_name('info')
                btn.has_focus = False
        elif kv == Gdk.KEY_Left: # left-key
            btn = tr.get_button_by_name('action0')
            btn.has_focus = False
            btn = tr.get_button_by_name('info')
            btn.has_focus = True
        elif kv == Gdk.KEY_space:  # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != Gtk.StateType.INSENSITIVE:
                    btn.set_state(Gtk.StateType.ACTIVE)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        #self._init_activated(btn, self.get_model(), path)
                        r = True
                    break

        self.queue_draw()
        return r

    def _on_key_release_event(self, widget, event, tr):
        kv = event.keyval
        r = False
        if kv == 32:    # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != Gtk.StateType.INSENSITIVE:
                    btn.set_state(Gtk.StateType.NORMAL)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    if path:
                        self._init_activated(btn, self.get_model(), path)
                        btn.has_focus = False
                        r = True
                    break

        self.queue_draw()
        return r

    def _init_activated(self, btn, model, path):
        app = model[path][AppGenericStore.COL_ROW_DATA]
        s = Gtk.Settings.get_default()
        GObject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self._app_activated_cb,
                            btn,
                            btn.name,
                            app,
                            model,
                            path)
        return

    def _cell_data_func_cb(self, col, cell, model, it, user_data):

        path = model.get_path(it)

        if model[path][0] is None:
            indices = path.get_indices()
            model.load_range(indices, 5)

        is_active = path == self.expanded_path
        cell.set_property('isactive', is_active)
        return

    def _app_activated_cb(self, btn, btn_id, app, store, path):
        if self.rowref_is_category(app): return

        pkgname = self.appmodel.get_pkgname(app)

        if btn_id == CellButtonIDs.INFO:
            self.emit("application-activated", self.appmodel.get_application(app))
        elif btn_id == CellButtonIDs.ACTION:
            btn.set_sensitive(False)
            store.row_changed(path, store.get_iter(path))
            # be sure we dont request an action for a pkg with pre-existing actions
            if pkgname in self._action_block_list:
                logging.debug("Action already in progress for package: '%s'" % pkgname)
                return False
            self._action_block_list.append(pkgname)
            if self.appmodel.is_installed(app):
                perform_action = AppActions.REMOVE
            else:
                perform_action = AppActions.INSTALL

            store.notify_action_request(app, path)

            self.emit("application-request-action",
                      self.appmodel.get_application(app),
                      [], [], perform_action)
        return False

    def _set_cursor(self, btn, cursor):
        # make sure we have a window instance (LP: #617004)
        window = self.get_window()
        if isinstance(window, Gdk.Window):
            x, y = self.get_pointer()
            if btn.point_in(x, y):
                window.set_cursor(cursor)

    def _on_transaction_started(self, backend, pkgname, appname, trans_id, trans_type, tr):
        """ callback when an application install/remove transaction has started """
        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            action_btn.set_sensitive(False)
            self._set_cursor(action_btn, None)

    def _on_transaction_finished(self, backend, result, tr):
        """ callback when an application install/remove transaction has finished """
        # need to send a cursor-changed so the row button is properly updated
        self.emit("cursor-changed")
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(result.pkgname)

        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _on_transaction_stopped(self, backend, result, tr):
        """ callback when an application install/remove transaction has stopped """
        # remove pkg from the block list
        self._check_remove_pkg_from_blocklist(result.pkgname)

        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            # this should be a function that decides action button state label...
            if action_btn.current_variant == 2:
                action_btn.set_markup_variant_n(1)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _on_net_state_changed(self, watcher, state, tr):
        self._update_selected_row(self, tr)
        # queue a draw just to be sure the view is looking right
        self.queue_draw()
        return

    def _check_remove_pkg_from_blocklist(self, pkgname):
        if pkgname in self._action_block_list:
            i = self._action_block_list.index(pkgname)
            del self._action_block_list[i]

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        #cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]


class AppViewFilter(xapian.MatchDecider):
    """
    Filter that can be hooked into xapian get_mset to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        xapian.MatchDecider.__init__(self)
        self.distro = get_distro()
        self.db = db
        self.cache = cache
        self.available_only = False
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
    @property
    def required(self):
        """ True if the filter is in a state that it should be part of a query """
        return (self.available_only or
                self.supported_only or
                self.installed_only or 
                self.not_installed_only)
    def set_available_only(self, v):
        self.available_only = v
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def get_supported_only(self):
        return self.supported_only
    def __eq__(self, other):
        if self is None and other is not None: 
            return True
        if self is None or other is None: 
            return False
        return (self.installed_only == other.installed_only and
                self.not_installed_only == other.not_installed_only and
                self.supported_only == other.supported_only)
    def __ne__(self, other):
        return not self.__eq__(other)
    def __call__(self, doc):
        """return True if the package should be displayed"""
        # get pkgname from document
        pkgname =  self.db.get_pkgname(doc)
        #logging.debug(
        #    "filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.available_only:
            # an item is considered available if it is either found
            # in the cache or is available for purchase
            if (not pkgname in self.cache and 
                not doc.get_value(XapianValues.ARCHIVE_CHANNEL) == AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME):
                return False
        if self.installed_only:
            # use the lowlevel cache here, twice as fast
            lowlevel_cache = self.cache._cache._cache
            if (not pkgname in lowlevel_cache or
                not lowlevel_cache[pkgname].current_ver):
                return False
        if self.not_installed_only:
            if (pkgname in self.cache and
                self.cache[pkgname].is_installed):
                return False
        if self.supported_only:
            if not self.distro.is_supported(self.cache, doc, pkgname):
                return False
        return True

def get_query_from_search_entry(search_term):
    if not search_term:
        return xapian.Query("")
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    return user_query

def on_entry_changed(widget, data):

    def _work():
        new_text = widget.get_text()
        (view, enquire) = data

        with ExecutionTime("total time"):
            with ExecutionTime("enquire.set_query()"):
                enquire.set_query(get_query_from_search_entry(new_text),
                                  limit=100*1000,
                                  nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE)

            store = view.get_model()
            with ExecutionTime("store.clear()"):
                store.clear()

            with ExecutionTime("store.set_documents()"):
                store.set_from_matches(enquirer.matches)

            with ExecutionTime("model settle (size=%s)" % len(store)):
                while Gtk.events_pending():
                    Gtk.main_iteration()
        return

    if widget.stamp: GObject.source_remove(widget.stamp)
    widget.stamp = GObject.timeout_add(250, _work)

if __name__ == "__main__":
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    softwarecenter.log.add_filters_from_string("performance")
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    # the store
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    # the db
    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = Gtk.IconTheme.get_default()
    icons.prepend_search_path("/usr/share/app-install/icons/")
    icons.prepend_search_path("/usr/share/software-center/icons/")

    # create a filter
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(True)

    # appview
    from softwarecenter.ui.gtk3.models.appstore2 import AppListStore
    from softwarecenter.db.enquire import AppEnquire
    enquirer = AppEnquire(cache, db)
    store = AppListStore(db, cache, icons)
    view = AppView(icons, show_ratings=True)
    view.set_model(store)

    entry = Gtk.Entry()
    entry.stamp = 0
    entry.connect("changed", on_entry_changed, (view, enquirer))
    entry.set_text("gtk3")

    scroll = Gtk.ScrolledWindow()
    box = Gtk.VBox()
    box.pack_start(entry, False, True, 0)
    box.pack_start(scroll, True, True, 0)

    win = Gtk.Window()
    win.connect("destroy", lambda x: Gtk.main_quit())
    scroll.add(view)
    win.add(box)
    win.set_size_request(600, 400)
    win.show_all()

    Gtk.main()

