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

from __future__ import with_statement

import gettext
import glib
import gobject
import gtk
import logging
import os
import pangocairo
import pango
import sys
import xapian

from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.backend import get_install_backend
from softwarecenter.db.database import StoreDatabase, Application

#from softwarecenter.db.reviews import get_review_loader
#from softwarecenter.backend import get_install_backend
#from softwarecenter.paths import SOFTWARE_CENTER_ICON_CACHE_DIR

from softwarecenter.distro import get_distro
from softwarecenter.models.appstore import AppStore

from widgets.mkit import get_em_value, get_mkit_theme, floats_from_gdkcolor_with_alpha, EM
from widgets.reviews import StarPainter

from gtk import gdk

from gettext import gettext as _


class CellRendererButton2:

    def __init__(self, name, markup=None, markup_variants=None, xpad=12, ypad=4, use_max_variant_width=True):
        # use_max_variant_width is currently ignored. assumed to be True

        self.name = name

        self.current_variant = 0
        if markup:
            self.markup_variants = (markup,)
        else:
            # expects a list or tuple!
            self.markup_variants = markup_variants

        self.xpad = xpad
        self.ypad = ypad
        self.allocation = gdk.Rectangle(0,0,1,1)
        self.state = gtk.STATE_NORMAL
        self.shape = 0
        self.has_focus = False

        self._widget = None
        self.theme = get_mkit_theme()
        return

    def _layout_reset(self, layout):
        layout.set_width(-1)
        layout.set_ellipsize(pango.ELLIPSIZE_NONE)
        self.layout = layout
        return


    # Part compat
    @property
    def is_active(self):
        return self.has_focus

    def configure_geometry(self, widget):
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)
        max_size = (0,0)
        for variant in self.markup_variants:
            layout.set_markup(gobject.markup_escape_text(variant))
            max_size = max(max_size, layout.get_pixel_extents()[1][2:])

        w, h = max_size
        self.set_size(w+2*self.xpad, h+2*self.ypad)
        return

    def point_in(self, x, y):
        return gdk.region_rectangle(self.allocation).point_in(x,y)

    def get_size(self):
        a = self.allocation
        return a.width, a.height 

    def set_position(self, x, y):
        a = self.allocation
        self.size_allocate(gdk.Rectangle(x, y, a.width, a.height))
        return

    def set_size(self, w, h):
        a = self.allocation
        self.size_allocate(gdk.Rectangle(a.x, a.y, w, h))
        return

    def size_allocate(self, rect):
        self.allocation = rect
        return

    def set_state(self, state):
        if state == self.state: return
        self.state = state
        if self._widget:
            self._widget.queue_draw_area(*self.get_allocation_tuple())
        return

    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            self.state = gtk.STATE_NORMAL
        else:
            self.state = gtk.STATE_INSENSITIVE
        if self._widget:
            self._widget.queue_draw_area(*self.get_allocation_tuple())
        return

    def set_markup(self, markup):
        self.markup_variant = (markup,)
        return

    def set_markup_variants(self, markup_variants):
        # expects a tuple or list
        self.markup_variants = markup_variants
        return

    def set_markup_variant_n(self, n):
        # yes i know this is totally hideous...
        if n >= len(self.markup_variants):
            print n, 'Not in range', self.markup_variants
            return
        self.current_variant = n
        return

    def get_allocation_tuple(self):
        a = self.allocation
        return (a.x, a.y, a.width, a.height)

    def render(self, window, widget, layout=None):
        if not self._widget:
            self._widget = widget
        if self.state != gtk.STATE_ACTIVE:
            shadow = gtk.SHADOW_OUT
        else:
            shadow = gtk.SHADOW_IN

        if not layout:
            pc = widget.get_pango_context()
            self.layout = pango.Layout(pc)
        else:
            self._layout_reset(layout)
        self.layout = layout

        layout.set_markup(self.markup_variants[self.current_variant])
        xpad, ypad = self.xpad, self.ypad
        x, y, w, h = self.get_allocation_tuple()

        # clear teh background first
        # this prevents the button overdrawing on its self,
        # which results in transparent pixels accumulating alpha value
        cr = window.cairo_create()
        #cr.set_operator(cairo.OPERATOR_CLEAR)
        cr.rectangle(x, y, w, h)
        cr.clip()
        #cr.paint_with_alpha(0)

        #cr.set_operator(cairo.OPERATOR_OVER)
        
        #widget.style.paint_box(window,
                               #self.state,
                               #shadow,
                               #(x, y, w, h),
                               #widget,
                               #"button",
                               #x, y, w, h)

        # use mkit to draw the cell renderer button. more reliable results
        self.theme.paint_bg(cr, self, x, y, w, h)

        # if we have more than one markup variant
        # we need to calc layout x-offset for current variant markup
        if len(self.markup_variants) > 1:
            lw = layout.get_pixel_extents()[1][2]
            xo = x + (w - lw)/2

        # else, we can just use xpad as the x-offset... 
        else:
            xo = x + xpad

        if self.has_focus and self.state != gtk.STATE_INSENSITIVE and \
            self._widget.has_focus():
            w, h = layout.get_pixel_extents()[1][2:]
            widget.style.paint_focus(window,
                                     self.state,
                                     (xo-3, y+ypad, w+6, h),
                                     widget,
                                     "expander",
                                     xo-3, y+ypad,
                                     w+6, h)

        # etch
        if not (self.has_focus and self.state == gtk.STATE_PRELIGHT):
            pcr = pangocairo.CairoContext(cr)
            pcr.move_to(xo, y+ypad+1)
            pcr.layout_path(layout)
            pcr.set_source_rgba(*floats_from_gdkcolor_with_alpha(widget.style.light[self.state], 0.5))
            pcr.fill()

        widget.style.paint_layout(window,
                                  self.state,
                                  True,
                                  (xo, y+ypad, w, h),
                                  widget,
                                  "button",
                                  xo, y+ypad,
                                  layout)
        return


# custom cell renderer to support dynamic grow
class CellRendererAppView2(gtk.CellRendererText):

    # offset of the install overlay icon
    OFFSET_X = 20
    OFFSET_Y = 20

    # size of the install overlay icon
    OVERLAY_SIZE = 16
    
    # ratings
    MAX_STARS = 5
    STAR_SIZE = int(1.15*EM)

    __gproperties__ = {
        'overlay' : (bool, 'overlay', 'show an overlay icon', False,
                     gobject.PARAM_READWRITE),

        'pixbuf' :  (gtk.gdk.Pixbuf, "Pixbuf", 
                    "Application icon pixbuf image", gobject.PARAM_READWRITE),

        # numbers mean: min: 0, max: 5, default: 0
        'rating': (gobject.TYPE_FLOAT, 'Rating', 'Avg rating', 0.0, 5.0, 0.0,
            gobject.PARAM_READWRITE),

        'nreviews': (gobject.TYPE_INT, 'Reviews', 'Number of reviews', 0, 100, 0,
            gobject.PARAM_READWRITE),

        'isactive': (bool, 'IsActive', 'Is active?', False,
                    gobject.PARAM_READWRITE),

        'installed': (bool, 'installed', 'Is the app installed', False,
                     gobject.PARAM_READWRITE),

        'available': (bool, 'available', 'Is the app available for install', False,
                     gobject.PARAM_READWRITE),

        'action_in_progress': (gobject.TYPE_INT, 'Action Progress', 'Action progress', -1, 100, -1,
                     gobject.PARAM_READWRITE),

        'exists': (bool, 'exists', 'Is the app found in current channel', False,
                   gobject.PARAM_READWRITE),

        # overload the native markup property becasue i didnt know how to read it
        # note; the 'text' attribute is used as the cell atk description
        'markup': (str, 'markup', 'The markup to paint', '',
                   gobject.PARAM_READWRITE)
        }

    def __init__(self, show_ratings, overlay_icon_name):
        gtk.CellRendererText.__init__(self)
        # geometry-state values
        self.overlay_icon_name = overlay_icon_name
        self.pixbuf_width = 0
        self.normal_height = 0
        self.selected_height = 0

        # attributes
        self.overlay = False
        self.pixbuf = None
        self.markup = ''
        self.rating = 0
        self.isactive = False
        self.installed = False
        self.show_ratings = show_ratings

        # button packing
        self.button_spacing = 0
        self._buttons = {gtk.PACK_START: [],
                         gtk.PACK_END:   []}
        self._all_buttons = {}

        # cache a layout
        self._layout = None
        self._nr_reviews_layout = None
        self._star_painter = StarPainter()

        # icon/overlay jazz
        icons = gtk.icon_theme_get_default()
        try:
            self._installed = icons.load_icon(overlay_icon_name,
                                              self.OVERLAY_SIZE, 0)
        except glib.GError:
            # icon not present in theme, probably because running uninstalled
            self._installed = icons.load_icon('emblem-system',
                                              self.OVERLAY_SIZE, 0)
        return

    def _layout_get_pixel_width(self, layout):
        return layout.get_pixel_extents()[1][2]

    def _layout_get_pixel_height(self, layout):
        return layout.get_pixel_extents()[1][3]

    def _render_icon(self, window, widget, cell_area, state, xpad, ypad, direction):
        # calc offsets so icon is nicely centered
        xo = (self.pixbuf_width - self.pixbuf.get_width())/2

        if direction != gtk.TEXT_DIR_RTL:
            x = xpad+xo
        else:
            x = cell_area.width+xo-self.pixbuf_width

        # draw appicon pixbuf
        window.draw_pixbuf(None,
                           self.pixbuf,             # icon
                           0, 0,                    # src pixbuf
                           x, cell_area.y+ypad,     # dest in window
                           -1, -1,                  # size
                           0, 0, 0)                 # dither

        # draw overlay if application is installed
        if self.overlay:
            if direction != gtk.TEXT_DIR_RTL:
                x = self.OFFSET_X
            else:
                x = cell_area.width - self.OVERLAY_SIZE

            y = cell_area.y + self.OFFSET_Y
            window.draw_pixbuf(None,
                               self._installed,     # icon
                               0, 0,                # src pixbuf
                               x, y,                # dest in window
                               -1, -1,              # size
                               0, 0, 0)             # dither
        return

    def _render_appsummary(self, window, widget, cell_area, state, layout, xpad, ypad, direction):
        # adjust cell_area

        # work out max allowable layout width
        lw = self._layout_get_pixel_width(layout)
        max_layout_width = cell_area.width - self.pixbuf_width - 3*xpad - self.MAX_STARS*self.STAR_SIZE

        if self.isactive and self.props.action_in_progress > 0:
            action_btn = self.get_button_by_name('action0')
            if not action_btn:
                logging.warn("No action button? This doesn't make sense!")
                return
            max_layout_width -= (xpad + action_btn.allocation.width) 

        if lw >= max_layout_width:
            layout.set_width((max_layout_width)*pango.SCALE)
            layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            lw = max_layout_width

        if direction != gtk.TEXT_DIR_RTL:
            x = 2*xpad+self.pixbuf_width
        else:
            x = cell_area.x+cell_area.width-lw-self.pixbuf_width-2*xpad

        y = cell_area.y+ypad

        w, h = lw, self.normal_height
        widget.style.paint_layout(window, state,
                                  False,
                                  (x, y, w, h),
                                  widget, None,
                                  x, y, layout)
        return

    def _render_rating(self, window, widget, state, cell_area, xpad, ypad, direction, spacing=3):
        # draw stars on the top right
        cr = window.cairo_create()

        # for the sake of aesthetics,
        # star width should be approx 1/5 the width of the action button
        sw = sh = self.get_button_by_name('action0').get_size()[0] / 5

        for i in range(0, self.MAX_STARS):
            x = cell_area.x + cell_area.width - xpad - (self.MAX_STARS-i)*sw
            y = cell_area.y + ypad
            if i < int(self.rating):
                self._star_painter.set_fill(StarPainter.FILL_FULL)
            elif (i == int(self.rating) and 
                  self.rating - int(self.rating) > 0):
                self._star_painter.set_fill(StarPainter.FILL_HALF)
            else:
                self._star_painter.set_fill(StarPainter.FILL_EMPTY)
            self._star_painter.paint_star(cr, widget, state, x, y, sw, sh)

        # and nr-reviews below
        if not self._nr_reviews_layout:
            self._nr_reviews_layout = widget.create_pango_layout('')
        s = gettext.ngettext(
            "%(nr_ratings)i Rating",
            "%(nr_ratings)i Ratings",
            self.nreviews) % { 'nr_ratings' : self.nreviews, }

        self._nr_reviews_layout.set_markup("<small>%s</small>" % s)
        # FIXME: improve w, h area calculation

        lw, lh = self._nr_reviews_layout.get_pixel_extents()[1][2:]

        w = self.MAX_STARS*sw

        x = cell_area.x + cell_area.width - xpad - w + (w-lw)/2
        y = cell_area.y + 2*ypad+sh

        clip_area = None#(x, y, w, h)
        widget.style.paint_layout(window, 
                                  state,
                                  True, 
                                  clip_area,
                                  widget,
                                  None, 
                                  x, 
                                  y, 
                                  self._nr_reviews_layout)
        return

    def _render_progress(self, window, widget, cell_area, ypad, direction):
        # as seen in gtk's cellprogress.c
        percent = self.props.action_in_progress * 0.01

        # per the spec, the progressbar should be the width of the action button
        action_btn = self.get_button_by_name('action0')
        if not action_btn:
            logging.warn("No action button? This doesn't make sense!")
            return

        x, y, w, h = action_btn.get_allocation_tuple()
        # shift the bar to the top edge
        y = cell_area.y + ypad

#        FIXME: GtkProgressBar draws the box with "trough" detail,
#        but some engines don't paint anything with that detail for
#        non-GtkProgressBar widgets.

        widget.style.paint_box(window,
                               gtk.STATE_NORMAL,
                               gtk.SHADOW_IN,
                               (x, y, w, h),
                               widget,
                               None,
                               x, y, w, h)

        if direction != gtk.TEXT_DIR_RTL:
            clip = gdk.Rectangle(x, y, int(w*percent), h)
        else:
            clip = gdk.Rectangle(x+(w-int(w*percent)), y, int(w*percent), h)

        widget.style.paint_box(window,
                               gtk.STATE_SELECTED,
                               gtk.SHADOW_OUT,
                               clip,
                               widget,
                               "bar",
                               clip.x, clip.y,
                               clip.width, clip.height)
        return

    def set_normal_height(self, h):
        self.normal_height = int(h)
        return

    def set_pixbuf_width(self, w):
        self.pixbuf_width = w
        return

    def set_selected_height(self, h):
        self.selected_height = h
        return

    def set_button_spacing(self, spacing):
        self.button_spacing = spacing
        return

    def get_button_by_name(self, name):
        if name in self._all_buttons:
            return self._all_buttons[name]
        return None

    def get_buttons(self):
        btns = ()
        for k, v in self._buttons.iteritems():
            btns += tuple(v)
        return btns

    def button_pack(self, btn, pack_type=gtk.PACK_START):
        self._buttons[pack_type].append(btn)
        self._all_buttons[btn.name] = btn
        return

    def button_pack_start(self, btn):
        self.button_pack(btn, gtk.PACK_START)
        return

    def button_pack_end(self, btn):
        self.button_pack(btn, gtk.PACK_END)
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def do_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')
        direction = widget.get_direction()

        # important! ensures correct text rendering, esp. when using hicolor theme
        if (flags & gtk.CELL_RENDERER_SELECTED) != 0:
            # this follows the behaviour that gtk+ uses for states in treeviews
            if widget.has_focus():
                state = gtk.STATE_SELECTED
            else:
                state = gtk.STATE_ACTIVE
        else:
            state = gtk.STATE_NORMAL

        if not self._layout:
            pc = widget.get_pango_context()
            self._layout = pango.Layout(pc)
            self._layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        self._render_icon(window, widget,
                          cell_area, state,
                          xpad, ypad,
                          direction)

        self._layout.set_markup(self.markup)
        self._render_appsummary(window, widget,
                                cell_area, state,
                                self._layout,
                                xpad, ypad,
                                direction)

        # only show ratings if we have one
        if  self.rating > 0 and self.props.action_in_progress < 0:
            self._render_rating(window, widget, state, cell_area, xpad, ypad, direction)

        # below is the stuff that is only done for the active cell
        if not self.isactive:
            return

        if self.props.action_in_progress > 0:
            self._render_progress(window, widget, cell_area, ypad, direction)

        # layout buttons and paint
        y = cell_area.y+cell_area.height-ypad
        spacing = self.button_spacing

        if direction != gtk.TEXT_DIR_RTL:
            start = gtk.PACK_START
            end = gtk.PACK_END
            xs = cell_area.x + 2*xpad + self.pixbuf_width
            xb = cell_area.x + cell_area.width - xpad
        else:
            start = gtk.PACK_END
            end = gtk.PACK_START
            xs = cell_area.x + xpad
            xb = cell_area.x + cell_area.width - 2*xpad - self.pixbuf_width

        for btn in self._buttons[start]:
            btn.set_position(xs, y-btn.allocation.height)
            btn.render(window, widget, self._layout)
            xs += btn.allocation.width + spacing

        for btn in self._buttons[end]:
            xb -= btn.allocation.width
            btn.set_position(xb, y-btn.allocation.height)
            if self.props.available:
                btn.render(window, widget, self._layout)
            else:
                btn.set_sensitive(False)
            xb -= spacing
        return

    def do_get_size(self, widget, cell_area):
        if not self.isactive:
            return -1, -1, -1, self.normal_height
        return -1, -1, -1, self.selected_height

gobject.type_register(CellRendererAppView2)



class AppView(gtk.TreeView):

    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT,
                                         gobject.TYPE_PYOBJECT, 
                                         gobject.TYPE_PYOBJECT,
                                         str),
                                       ),
    }

    def __init__(self, show_ratings, store=None):
        gtk.TreeView.__init__(self)
        self._logger = logging.getLogger("softwarecenter.view.appview")
        #self.buttons = {}
        self.pressed = False
        self.focal_btn = None
        self._action_block_list = []

        # if this hacked mode is available everything will be fast
        # and we can set fixed_height mode and still have growing rows
        # (see upstream gnome #607447)
        try:
            self.set_property("ubuntu-almost-fixed-height-mode", True)
            self.set_fixed_height_mode(True)
        except:
            self._logger.warn("ubuntu-almost-fixed-height-mode extension not available")

        self.set_headers_visible(False)

        # disable search that works by typing, it will be super slow
        # the way that its done by gtk and we have much faster searching
        self.set_enable_search(False)
        #self.set_search_column(AppStore.COL_PKGNAME)

        # a11y: this is a cell renderer that only displays a icon, but still
        #       has a markup property for orca and friends
        # we use it so that orca and other a11y tools get proper text to read
        # it needs to be the first one, because that is what the tools look
        # at by default

        tr = CellRendererAppView2(show_ratings, "software-center-installed")
        tr.set_pixbuf_width(32)
        tr.set_button_spacing(int(get_em_value()*0.3+0.5))

        # translatable labels for cell buttons
        # string for info button, currently does not need any variants
        self._info_str = _('More Info')

        # string for action button
        # needs variants for the current label states: install, remove & pending
        self._action_strs = {'install' : _('Install'),
                             'remove'  : _('Remove')}

        # create buttons and set initial strings
        info = CellRendererButton2(name='info', markup=self._info_str)
        variants = (self._action_strs['install'],
                    self._action_strs['remove'])
        action = CellRendererButton2(name='action0', markup_variants=variants)

        tr.button_pack_start(info)
        tr.button_pack_end(action)

        column = gtk.TreeViewColumn("Available Apps", tr,
                                    pixbuf=AppStore.COL_ICON,
                                    overlay=AppStore.COL_INSTALLED,
                                    text=AppStore.COL_ACCESSIBLE,
                                    markup=AppStore.COL_MARKUP,
                                    rating=AppStore.COL_RATING,
                                    nreviews=AppStore.COL_NR_REVIEWS,
                                    isactive=AppStore.COL_IS_ACTIVE,
                                    installed=AppStore.COL_INSTALLED, 
                                    available=AppStore.COL_AVAILABLE,
                                    action_in_progress=AppStore.COL_ACTION_IN_PROGRESS,
                                    exists=AppStore.COL_EXISTS)

        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        if store is None:
            store = gtk.ListStore(str, gtk.gdk.Pixbuf)
        self.set_model(store)

        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated, tr)

        # button and motion are "special"
        self.connect("style-set", self._on_style_set, tr)

        self.connect("button-press-event", self._on_button_press_event, tr)
        self.connect("button-release-event", self._on_button_release_event, tr)

        self.connect("key-press-event", self._on_key_press_event, tr)
        self.connect("key-release-event", self._on_key_release_event, tr)

        self.connect("cursor-changed", self._on_cursor_changed, tr)
        self.connect("motion-notify-event", self._on_motion, tr)

        self.backend = get_install_backend()
        self._transactions_connected = False
        self.connect('realize', self._on_realize, tr)

    def set_model(self, new_model):
        # unset
        if new_model is None:
            super(AppView, self).set_model(None)
        # Only allow use of an AppStore model
        if type(new_model) != AppStore:
            return
        return super(AppView, self).set_model(new_model)
        
    def clear_model(self):
        self.set_model(None)

    def is_action_in_progress_for_selected_app(self):
        """
        return True if an install or remove of the current package
        is in progress
        """
        (path, column) = self.get_cursor()
        model = self.get_model()
        if path:
            return (model[path][AppStore.COL_ACTION_IN_PROGRESS] != -1)
        return False

    def _on_realize(self, widget, tr):
        # connect to backend events once self is realized so handlers 
        # have access to the TreeView's initialised gtk.gdk.Window
        if self._transactions_connected: return
        self.backend.connect("transaction-started", self._on_transaction_started, tr)
        self.backend.connect("transaction-finished", self._on_transaction_finished, tr)
        self.backend.connect("transaction-stopped", self._on_transaction_stopped, tr)
        self._transactions_connected = True
        return

    def _on_style_set(self, widget, old_style, tr):
        em = get_em_value()

        pad = int(em*0.3)
        tr.set_property('xpad', pad)
        tr.set_property('ypad', pad)

        for btn in tr.get_buttons():
            # recalc button geometry and cache
            btn.configure_geometry(self)

        btn_h = btn.allocation.height

        normal_height = int(2.5*em + pad)
        tr.set_normal_height(max(32 + 2*pad, normal_height))
        tr.set_selected_height(int(normal_height + btn_h + 3*pad))
        return

    def _on_motion(self, tree, event, tr):
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y):
            self.window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path: return

        use_hand = False
        for btn in tr.get_buttons():
            if btn.state != gtk.STATE_INSENSITIVE:
                if btn.point_in(x, y):
                    if self.focal_btn is btn:
                        use_hand = True
                        btn.set_state(gtk.STATE_ACTIVE)
                    elif not self.pressed:
                        use_hand = True
                        btn.set_state(gtk.STATE_PRELIGHT)
                else:
                    if btn.state != gtk.STATE_NORMAL:
                        btn.set_state(gtk.STATE_NORMAL)

        if use_hand:
            self.window.set_cursor(self._cursor_hand)
        else:
            self.window.set_cursor(None)
        return

    def _on_cursor_changed(self, view, tr):
        model = view.get_model()
        sel = view.get_selection()
        path = view.get_cursor()[0] or (0,)
        sel.select_path(path)
        self._update_selected_row(view, tr)

    def _update_selected_row(self, view, tr):
        sel = view.get_selection()
        if not sel:
            return False
        model, rows = sel.get_selected_rows()
        if not rows: 
            return False

        row = rows[0][0]
        # update active app, use row-ref as argument
        model._set_active_app(row)
        installed = model[row][AppStore.COL_INSTALLED]

        action_btn = tr.get_button_by_name('action0')
        #if not action_btn: return False

        if self.is_action_in_progress_for_selected_app():
            action_btn.set_sensitive(False)
        elif self.pressed and self.focal_btn == action_btn:
            action_btn.set_state(gtk.STATE_ACTIVE)
        else:
            action_btn.set_state(gtk.STATE_NORMAL)

        if installed:
            action_btn.set_markup_variant_n(1)
            #action_btn.configure_geometry(self)
        else:
            action_btn.set_markup_variant_n(0)
            #action_btn.configure_geometry(self)

        name = model[row][AppStore.COL_APP_NAME]
        pkgname = model[row][AppStore.COL_PKGNAME]
        request = model[row][AppStore.COL_REQUEST]
        self.emit("application-selected", Application(name, pkgname, request))
        return False

    def _on_row_activated(self, view, path, column, tr):
        pointer = gtk.gdk.device_get_core_pointer()
        x, y = pointer.get_state(view.window)[0]
        for btn in tr.get_buttons():
            if btn.point_in(int(x), int(y)): 
                return

        model = view.get_model()
        exists = model[path][AppStore.COL_EXISTS]
        if exists:
            name = model[path][AppStore.COL_APP_NAME]
            pkgname = model[path][AppStore.COL_PKGNAME]
            request = model[path][AppStore.COL_REQUEST]
            self.emit("application-activated", Application(name, pkgname, request))

    def _on_button_press_event(self, view, event, tr):
        if event.button != 1:
            return
        self.pressed = True
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        path = res[0]
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != gtk.STATE_INSENSITIVE):
                self.focal_btn = btn
                btn.set_state(gtk.STATE_ACTIVE)
                return
        self.focal_btn = None

    def _on_button_release_event(self, view, event, tr):
        if event.button != 1:
            return
        self.pressed = False
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        path = res[0]
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        for btn in tr.get_buttons():
            if btn.point_in(x, y) and (btn.state != gtk.STATE_INSENSITIVE):
                btn.set_state(gtk.STATE_NORMAL)
                self.window.set_cursor(self._cursor_hand)
                if self.focal_btn is not btn:
                    break
                self._init_activated(btn, view.get_model(), path)
                break
        self.focal_btn = None

    def _on_key_press_event(self, widget, event, tr):
        kv = event.keyval
        #print kv
        r = False
        if kv == gtk.keysyms.Right: # right-key
            btn = tr.get_button_by_name('action0')
            if btn.state != gtk.STATE_INSENSITIVE:
                btn.has_focus = True
                btn = tr.get_button_by_name('info')
                btn.has_focus = False
        elif kv == gtk.keysyms.Left: # left-key
            btn = tr.get_button_by_name('action0')
            btn.has_focus = False
            btn = tr.get_button_by_name('info')
            btn.has_focus = True
        elif kv == gtk.keysyms.space:  # spacebar
            for btn in tr.get_buttons():
                if btn.has_focus and btn.state != gtk.STATE_INSENSITIVE:
                    btn.set_state(gtk.STATE_ACTIVE)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    #print model[path][AppStore.COL_APP_NAME]
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
                if btn.has_focus and btn.state != gtk.STATE_INSENSITIVE:
                    btn.set_state(gtk.STATE_NORMAL)
                    sel = self.get_selection()
                    model, it = sel.get_selected()
                    path = model.get_path(it)
                    #print model[path][AppStore.COL_APP_NAME]
                    if path:
                        self._init_activated(btn, self.get_model(), path)
                        btn.has_focus = False
                        r = True
                    break

        self.queue_draw()
        return r

    def _init_activated(self, btn, model, path):

        appname = model[path][AppStore.COL_APP_NAME]
        pkgname = model[path][AppStore.COL_PKGNAME]
        request = model[path][AppStore.COL_REQUEST]
        installed = model[path][AppStore.COL_INSTALLED]

        s = gtk.settings_get_default()
        gobject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self._app_activated_cb,
                            btn,
                            btn.name,
                            appname,
                            pkgname,
                            request,
                            installed,
                            model,
                            path)
        return

    def _app_activated_cb(self, btn, btn_id, appname, pkgname, request, installed, store, path):
        if btn_id == 'info':
            self.emit("application-activated", Application(appname, pkgname, request))
        elif btn_id == 'action0':
            btn.set_sensitive(False)
            store.row_changed(path[0], store.get_iter(path[0]))
            # be sure we dont request an action for a pkg with pre-existing actions
            if pkgname in self._action_block_list:
                logging.debug("Action already in progress for package: '%s'" % pkgname)
                return False
            self._action_block_list.append(pkgname)
            if installed:
                perform_action = APP_ACTION_REMOVE
            else:
                perform_action = APP_ACTION_INSTALL
            self.emit("application-request-action", Application(appname, pkgname, request), [], [], perform_action)
        return False

    def _set_cursor(self, btn, cursor):
        # make sure we have a window instance (LP: #617004)
        if isinstance(self.window, gtk.gdk.Window):
            pointer = gtk.gdk.device_get_core_pointer()
            x, y = pointer.get_state(self.window)[0]
            if btn.point_in(int(x), int(y)):
                self.window.set_cursor(cursor)

    def _on_transaction_started(self, backend, pkgname, tr):
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
        if isinstance(result, str):
            self._check_remove_pkg_from_blocklist(result)
        else:
            self._check_remove_pkg_from_blocklist(result.pkgname)

        action_btn = tr.get_button_by_name('action0')
        if action_btn:
            # this should be a function that decides action button state label...
            if action_btn.current_variant == 2:
                action_btn.set_markup_variant_n(1)
            action_btn.set_sensitive(True)
            self._set_cursor(action_btn, self._cursor_hand)

    def _check_remove_pkg_from_blocklist(self, pkgname):
        if pkgname in self._action_block_list:
            i = self._action_block_list.index(pkgname)
            del self._action_block_list[i]

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        cur = self.get_cursor()
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
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
    @property
    def required(self):
        """ True if the filter is in a state that it should be part of a query """
        return (self.supported_only or
                self.installed_only or 
                self.not_installed_only)
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
                self.not_installed_only == other.not_installed_only)
    def __ne__(self, other):
        return not self.__eq__(other)
    def __call__(self, doc):
        """return True if the package should be displayed"""
        # get pkgname from document
        pkgname =  self.db.get_pkgname(doc)
        #logging.debug(
        #    "filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
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
    new_text = widget.get_text()
    #if len(new_text) < 3:
    #    return
    (cache, db, view, filter) = data
    query = get_query_from_search_entry(new_text)
    view.set_model(_get_model_from_query(filter, query))
    with ExecutionTime("model settle"):
        while gtk.events_pending():
            gtk.main_iteration()

def _get_model_from_query(filter, query):
    return AppStore(cache, db, icons, query,
                    filter=filter, limit=0,
                    nonapps_visible=AppStore.NONAPPS_ALWAYS_VISIBLE)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    # the store
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()
    cache.open()

    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.prepend_search_path("/usr/share/app-install/icons/")
    icons.prepend_search_path("/usr/share/software-center/icons/")

    # create a filter
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(True)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(_get_model_from_query(filter, xapian.Query("")))

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (cache, db, view, filter))
    entry.set_text("a")

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(600, 400)
    win.show_all()

    gtk.main()

