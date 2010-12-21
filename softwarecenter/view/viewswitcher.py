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
import gobject
import gtk
import pango
import logging
import os
import cairo

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.db.database import StoreDatabase
from softwarecenter.models.viewswitcherlist import ViewSwitcherList
from softwarecenter.enums import *
from softwarecenter.utils import wait_for_apt_cache_ready

from widgets.animatedimage import CellRendererAnimatedImage, AnimatedImage
from widgets.mkit import ShapeRoundedRectangle, floats_from_gdkcolor

LOG = logging.getLogger(__name__)


class ViewItemCellRenderer(gtk.CellRendererText):

    """ A cell renderer that displays text and an action count bubble that
        displays if the item has an action occuring.
    """

    __gproperties__ = {
        
        'bubble_text': (str, 'Bubble text',
                        'Text to be label inside row bubble',
                        '', gobject.PARAM_READWRITE),
        }

    def __init__(self):
        gtk.CellRendererText.__init__(self) 
        self._rr = ShapeRoundedRectangle()
        self._layout = None
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):

        # important! ensures correct text rendering, esp. when using hicolor theme
        if (flags & gtk.CELL_RENDERER_SELECTED) != 0:
            # this follows the behaviour that gtk+ uses for states in treeviews
            if widget.has_focus():
                state = gtk.STATE_SELECTED
            else:
                state = gtk.STATE_ACTIVE
        else:
            state = gtk.STATE_NORMAL

        text = self.get_property('bubble_text')

        if text:

            if not self._layout:
                self._layout = widget.create_pango_layout('')

            # setup layout and determine layout extents
            color = widget.style.black.to_string()
            self._layout.set_markup('<span color="%s"><small><b>%s</b></small></span>' % (color, text))
            lw, lh = self._layout.get_pixel_extents()[1][2:]

            w = max(16, lw+8)
            h = min(cell_area.height-8, lh+8)

            # shrink text area width to make room for the bubble
            area = gtk.gdk.Rectangle(cell_area.x, cell_area.y,
                                     cell_area.width-w-9,
                                     cell_area.height)
        else:
            area = cell_area

        # draw text
        gtk.CellRendererText.do_render(self,
                                       window,
                                       widget,
                                       background_area,
                                       area,
                                       expose_area,
                                       state)

        # draw bubble
        if not text: return

        cr = window.cairo_create()

        # draw action bubble background
        x = max(3, cell_area.x + cell_area.width - w)
        y = cell_area.y + (cell_area.height-h)/2

        self._rr.layout(cr, x, y, x+w, y+h, radius=7)
        cr.set_source_rgb(*floats_from_gdkcolor(widget.style.dark[state]))
        cr.fill_preserve()

        lin = cairo.LinearGradient(0, y, 0, y+h)
        lin.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
        lin.add_color_stop_rgba(1.0, 0, 0, 0, 0.25)
        cr.set_source(lin)
        cr.fill_preserve()

        x, y = int(x+(w-lw)*0.5+0.5), int(y+(h-lh)*0.5+0.5),
                                  

        # bubble number shadow
        widget.style.paint_layout(window,
                                  gtk.STATE_NORMAL,
                                  False,
                                  cell_area,
                                  widget,
                                  None,
                                  x, y+1,
                                  self._layout)


        # bubble number
        color = widget.style.white.to_string()
        self._layout.set_markup('<span color="%s"><small><b>%s</b></small></span>' % (color, text))

        widget.style.paint_layout(window,
                                  gtk.STATE_NORMAL,
                                  False,
                                  cell_area,
                                  widget,
                                  None,
                                  x, y,
                                  self._layout)

        del cr
        return



class ViewSwitcher(gtk.TreeView):

    __gsignals__ = {
        "view-changed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT),
                         ),
    }


    def __init__(self, view_manager, datadir, db, cache, icons, store=None):
        super(ViewSwitcher, self).__init__()
        self.view_manager = view_manager
        self.datadir = datadir
        self.icons = icons
        self.cache = cache
        if not store:
            store = ViewSwitcherList(view_manager, datadir, db, cache, icons)
            # FIXME: this is just set here for app.py, make the
            #        transactions-changed signal part of the view api
            #        instead of the model
            self.model = store
            self.set_model(store)
        gtk.TreeView.__init__(self)
        
        tp = CellRendererAnimatedImage()
        column = gtk.TreeViewColumn("Icon")
        column.pack_start(tp, expand=False)
        column.set_attributes(tp, image=store.COL_ICON)
        tr = ViewItemCellRenderer()
        tr.set_property("ellipsize", pango.ELLIPSIZE_END)
        column.pack_start(tr, expand=True)
        column.set_attributes(tr, markup=store.COL_NAME, bubble_text=store.COL_BUBBLE_TEXT)
        self.append_column(column)

        # Remember the previously selected permanent view
        self._permanent_views = PERMANENT_VIEWS
        self._previous_permanent_view = None

        # set sensible atk name
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Software sources"))
        
        self.set_model(store)
        self.set_headers_visible(False)
        self.get_selection().set_select_function(self.on_treeview_selected)
        self.set_level_indentation(4)
        self.set_enable_search(False)

        self.selected_channel_name = None
        self.selected_channel_installed_only = False
        
        self.connect("row-expanded", self.on_treeview_row_expanded)
        self.connect("row-collapsed", self.on_treeview_row_collapsed)
        self.connect("cursor-changed", self.on_cursor_changed)
        self.connect("key-release-event", self.on_key_release_event)

        self.get_model().connect("channels-refreshed", self._on_channels_refreshed)
        self.get_model().connect("row-deleted", self._on_row_deleted)
        # channels changed
        self.backend = get_install_backend()
        self.backend.connect("channels-changed", self.on_channels_changed)
        self._block_set_cursor_signals = False
        
    def on_channels_changed(self, backend, res):
        LOG.debug("on_channels_changed %s" % res)
        if not res:
            return
        # update channel list, but block signals so that the cursor
        # does not jump around
        self._block_set_cursor_signals = True
        model = self.get_model()
        if model:
            model._update_channel_list()
        self._block_set_cursor_signals = False

    def on_treeview_row_expanded(self, widget, iter, path):
        # do nothing on a node expansion
        pass
        
    def on_treeview_row_collapsed(self, widget, iter, path):
        # on a node collapse, select the node
        self.set_cursor(path)
    
    def on_treeview_selected(self, path):
        model = self.get_model()
        iter_ = model.get_iter(path)
        id_ = model.get_value(iter_, 2)
        if id_ == VIEW_PAGE_SEPARATOR_1:
            return False
        return True
        
    def on_cursor_changed(self, widget):
        if self._block_set_cursor_signals:
            return
        (path, column) = self.get_cursor()
        if not path:
            return
        model = self.get_model()
        if not model:
            return
        action = model[path][ViewSwitcherList.COL_ACTION]
        channel = model[path][ViewSwitcherList.COL_CHANNEL]
        if action in self._permanent_views:
            self._previous_permanent_view = path
        self.selected_channel_name = model[path][ViewSwitcherList.COL_NAME]
        if channel:
            self.selected_channel_installed_only = channel.installed_only

        view_page = action
        self.emit("view-changed", view_page, channel)
        
    def on_key_release_event(self, widget, event):
        # Get the toplevel node of the currently selected row
        toplevel = self.get_toplevel_node(self.get_cursor())
        if toplevel is None:
            return
        toplevel_path = (toplevel,)

        # Expand the toplevel node if the right arrow key is clicked
        if event.keyval == gtk.keysyms.Right:
            if not self.row_expanded(toplevel_path):
                self.expand_row(toplevel_path, False)
        # Collapse the toplevel node if the left arrow key is clicked
        elif event.keyval == gtk.keysyms.Left:
            if self.row_expanded(toplevel_path):
                self.collapse_row(toplevel_path)
        return False
        
    def get_view(self):
        """return the current activated view number or None if no
           view is activated (this can happen when a pending view 
           disappeared). Views are:
           
           VIEW_PAGE_AVAILABLE
           VIEW_PAGE_CHANNEL
           VIEW_PAGE_INSTALLED
           VIEW_PAGE_HISTORY
           VIEW_PAGE_PENDING
        """
        (path, column) = self.get_cursor()
        if not path:
            return None
        return path[0]
    
    def get_toplevel_node(self, cursor):
        """Returns the toplevel node of a selected row"""
        (path, column) = cursor
        if not path:
            return None
        return path[0]

    def set_view(self, view_page):
        notebook_page_id = self.view_manager.get_notebook_page_from_view_id(view_page)
        # FIXME: This isn't really the cleanest way to do this, but afaics it is the only way to achieve this with the current view_manager
        if view_page == 'view-page-available':
            self.set_cursor((notebook_page_id,))
        else:
            self.set_cursor((notebook_page_id - 1,))
        self.emit("view-changed", view_page, None)

    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
            
    @wait_for_apt_cache_ready
    def expand_available_node(self):
        """ expand the available pane node in the viewswitcher pane """
        model = self.get_model()
        if model:
            self.expand_row(model.get_path(model.available_iter), False)
            
    def is_available_node_expanded(self):
        """ return True if the available pane node in the viewswitcher pane 
            is expanded 
        """
        model = self.get_model()
        expanded = False
        if model:
            expanded = self.row_expanded(model.get_path(model.available_iter))
        return expanded
        
    @wait_for_apt_cache_ready
    def expand_installed_node(self):
        """ expand the installed pane node in the viewswitcher pane """
        model = self.get_model()
        if model:
            self.expand_row(model.get_path(model.installed_iter), False)
            
    def is_installed_node_expanded(self):
        """ return True if the installed pane node in the viewswitcher pane 
            is expanded 
        """
        model = self.get_model()
        expanded = False
        if model:
            expanded = self.row_expanded(model.get_path(model.installed_iter))
        return expanded
        
    def select_available_node(self):
        """ select the top level available (Get Software) node """
        model = self.get_model()
        if model is not None:
            (current_path, column) = self.get_cursor()
            available_node_path = model.get_path(model.available_iter)
            if current_path != available_node_path:
                print "SELECT available node"
                self.set_cursor(model.get_path(model.available_iter))
        
    def select_channel_node(self, channel_name, installed_only):
        """ select the specified channel node """
        model = self.get_model()
        if model is not None:
            channel_iter_to_select = model.get_channel_iter_for_name(
                channel_name, installed_only)
            if channel_iter_to_select:
                self.set_cursor(model.get_path(channel_iter_to_select))

    def _on_channels_refreshed(self, model):
        """
        when channels are refreshed, the viewswitcher channel is unselected so
        we need to reselect it
        """
        model = self.get_model()
        if model:
            channel_iter_to_select = model.get_channel_iter_for_name(
                self.selected_channel_name,
                self.selected_channel_installed_only)
            if channel_iter_to_select:
                self._block_set_cursor_signals = True
                self.set_cursor(model.get_path(channel_iter_to_select))
                self._block_set_cursor_signals = False

    def _on_row_deleted(self, widget, deleted_path):
        (path, column) = self.get_cursor()
        if path is None:
            LOG.debug("path from _on_row_deleted no longer available")
            # The view that was selected has been deleted, switch back to
            # the previously selected permanent view.
            if self._previous_permanent_view is not None:
                self.set_cursor(self._previous_permanent_view)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    scroll = gtk.ScrolledWindow()
    icons = gtk.icon_theme_get_default()

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache(apt.progress.text.OpProgress())
    db = StoreDatabase(pathname, cache)
    db.open()

    from viewmanager import ViewManager
    notebook = gtk.Notebook()
    manager = ViewManager(notebook)
    view = ViewSwitcher(manager, datadir, db, cache, icons)

    box = gtk.VBox()
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
