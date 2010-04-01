# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import atk
import cairo
import gobject
import gtk
import pango
import pathbar_common

from gettext import gettext as _


class PathBar(gtk.HBox):

    def __init__(self, group=None):
        gtk.HBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_reallocate_redraws(False)

        self._width = 0
        self._queue = []
        self._active_part = None
        self._out_of_width = False
        self._button_press_origin = None

        self.theme = pathbar_common.PathBarStyle(self)

        # Accessibility info
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("You are here:"))
        atk_desc.set_role(atk.ROLE_PANEL)

        self.set_events(gtk.gdk.EXPOSURE_MASK)
        self.connect('expose-event', self._on_expose_event)
        self.connect('size-allocate', self._on_size_allocate)
        self.connect('realize', self._append_on_realize)
        return

    def _shrink_check(self, allocation):
        path_w = self._width
        overhang = path_w - allocation.width
        self._width -= overhang
        mpw = self.theme['min_part_width']
        for part in self.get_children():
            w = part.get_size_request()[0]
            dw = 0
            if w - overhang <= mpw:
                overhang -= w-mpw
                part.set_width(mpw)
            else:
                part.set_width(w-overhang)
                break
        self._out_of_width = True
        return

    def _grow_check(self, allocation):
        underhang = allocation.width - self._width
        parts = self.get_children()
        parts.reverse()
        for part in parts:
            bw = part.get_best_width()
            w = part.get_size_request()[0]
            if w < bw:
                dw = bw - w
                if dw <= underhang:
                    underhang -= dw
                    part.set_width(bw)
                else:
                    part.set_width(w + underhang)
                    underhang = 0
                    break
        self._width = allocation.width - underhang
        self._out_of_width = False
        return

    def _compose_on_append(self, last_part):
        parts = self.get_children()
        if len(parts) == 0:
            last_part.set_shape(pathbar_common.SHAPE_RECTANGLE)
        elif len(parts) == 1:
            root_part = parts[0]
            root_part.set_shape(pathbar_common.SHAPE_START_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        else:
            tail_part = parts[-1]
            tail_part.set_shape(pathbar_common.SHAPE_MID_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        return

    def _compose_on_remove(self, last_part):
        parts = self.get_children()
        if len(parts) == 1:
            last_part.set_shape(pathbar_common.SHAPE_RECTANGLE)
        elif len(parts) == 2:
            root_part = parts[0]
            root_part.set_shape(pathbar_common.SHAPE_START_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        else:
            tail_part = parts[-1]
            tail_part.set_shape(pathbar_common.SHAPE_MID_ARROW)
            last_part.set_shape(pathbar_common.SHAPE_END_CAP)
        return

    def _part_enter_notify(self, part, event):
        if part == self._button_press_origin:
            part.set_state(gtk.STATE_ACTIVE)
        else:
            part.set_state(gtk.STATE_PRELIGHT)
        self._part_queue_draw(part)
        return

    def _part_leave_notify(self, part, event):
        if part == self._active_part:
            part.set_state(gtk.STATE_SELECTED)
        else:
            part.set_state(gtk.STATE_NORMAL)
        self._part_queue_draw(part)
        return

    def _part_button_press(self, part, event):
        if event.button != 1: return
        self._button_press_origin = part
        part.set_state(gtk.STATE_ACTIVE)
        self._part_queue_draw(part)
        return

    def _part_button_release(self, part, event):
        if event.button != 1: return

        part_region = gtk.gdk.region_rectangle(part.allocation)
        if not part_region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            return
        if part != self._button_press_origin: return
        if self._active_part:
            self._active_part.set_state(gtk.STATE_NORMAL)
            self._part_queue_draw(self._active_part)

        self.set_active(part)
        part.set_state(gtk.STATE_PRELIGHT)
        self._button_press_origin = None
        self._part_queue_draw(part)
        return

    def _part_connect_signals(self, part):
        part.connect('enter-notify-event', self._part_enter_notify)
        part.connect('leave-notify-event', self._part_leave_notify)
        part.connect("button-press-event", self._part_button_press)
        part.connect("button-release-event", self._part_button_release)
        return

    def _part_queue_draw(self, part):
        a = part.get_allocation()
        x, y, h = a.x, a.y, a.height
        w = part.get_draw_width()
        xo = part.get_draw_xoffset()
        self.queue_draw_area(x+xo, y, w, h)
        return

    def _on_expose_event(self, widget, event):
        parts = self.get_children()
        parts.reverse()

        cr = widget.window.cairo_create()
        for part in parts:
            a = part.get_allocation()
            x, y, w, h = a.x, a.y, a.width, a.height
            w = part.get_draw_width()
            xo = part.get_draw_xoffset()
            self.theme.paint_bg(cr, part, x+xo, y, w, h)
            x, y, w, h = part.get_layout_points()
            self.theme.paint_layout(widget, widget.window, part, a.x+x, a.y+y, w, h)
        return

    def _on_size_allocate(self, widget, allocation):
        if self._width < allocation.width and self._out_of_width:
            self._grow_check(allocation)
        elif self._width >= allocation.width:
            self._shrink_check(allocation)
        return

    def _append_on_realize(self, widget):
        for part, do_callback, animate in self._queue:
            self.append(part, do_callback, animate)
        return

    def get_parts(self):
        return self.get_children()

    def set_active(self, part, do_callback=True):
        if part == self._active_part: return
        if self._active_part:
            self._active_part.set_state(gtk.STATE_NORMAL)
            self._part_queue_draw(self._active_part)

        part.set_state(gtk.STATE_SELECTED)
        self._part_queue_draw(part)
        self._active_part = part
        if do_callback and part.callback:
            part.callback(self, part)
        return

    def get_active(self):
        return self._active_part

    def set_active_no_callback(self, part):
        self.set_active(part, False)
        return

    def append(self, part, do_callback=True, animate=True):
        if not self.get_property('visible'):
            self._queue.append([part, do_callback, animate])
            return

        self._compose_on_append(part)
        self._width += part.get_size_request()[0]

        self.pack_start(part, False)
        self._part_connect_signals(part)
        part.show()

        if do_callback:
            self.set_active(part)
        else:
            self.set_active_no_callback(part)
        return

    def append_no_callback(self, part):
        self.append(part, do_callback=False)

    def remove(self, part):
        parts = self.get_children()
        if len(parts) == 1: return  # protect last part
        self._width -= part.get_size_request()[0]
        part.destroy()
        self._compose_on_remove(parts[-2])
        return

    def remove_all(self, keep_first_part=True, do_callback=True):
        parts = self.get_children()
        if len(parts) < 1: return
        if keep_first_part:
            if len(parts) <= 1: return
            parts = parts[1:]
        for part in parts:
            part.destroy()

        self._width = 0
        if keep_first_part:
            root = self.get_parts()[0]
            root.set_shape(pathbar_common.SHAPE_RECTANGLE)
            self._width = root.get_size_request()[0]
            if do_callback: root.callback(self, root)
        return

    def navigate_up(self):
        parts = self.get_children()
        if len(parts) > 1:
            nav_part = parts[len(parts) - 2]
            self.set_active(nav_part)
        return


class PathPart(gtk.EventBox):

    def __init__(self, parent, label, callback=None):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        part_atk = self.get_accessible()
        part_atk.set_name(label)
        part_atk.set_description(_('Click here to navigate to the %s page' % label))
        part_atk.set_role(atk.ROLE_PUSH_BUTTON)

        self._parent = parent
        self._draw_shift = 0
        self._draw_width = 0
        self._layout_points = 0,0,0,0
        self._size_requisition = 0,0

        self.shape = pathbar_common.SHAPE_RECTANGLE
        self.layout = None
        self.set_label(label)
        self.callback = callback

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)
        return

    def __repr__(self):
        BOLD = "\033[1m"
        RESET = "\033[0;0m"
        if self.shape == pathbar_common.SHAPE_RECTANGLE:
            s = '[ %s ]'
        elif self.shape == pathbar_common.SHAPE_START_ARROW:
            s = '[ %s }'
        elif self.shape == pathbar_common.SHAPE_MID_ARROW:
            s = '%s }'
        elif self.shape == pathbar_common.SHAPE_END_CAP:
            s = '%s ]'
        s = BOLD + s + RESET
        return s % self.label

    def _make_layout(self):
        pc = self._parent.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.label)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        self.layout = layout
        return

    def _calc_layout_points(self):
        if not self.layout: self._make_layout()
        x = self._parent.theme['xpad']
        y = self._parent.theme['ypad']
        w, h = self.layout.get_pixel_extents()[1][2:]
        self._layout_points = [x, y, w, h]
        return

    def _adjust_width(self, shape, w):
        arrow_width = self._parent.theme['arrow_width']
        if shape == pathbar_common.SHAPE_RECTANGLE:
            return w

        elif shape == pathbar_common.SHAPE_START_ARROW:
            self._draw_width += arrow_width
            if self.get_direction() == gtk.TEXT_DIR_RTL:
                self._draw_xoffset -= arrow_width
                self._layout_points[2] += self._parent.theme['xpad']

        elif shape == pathbar_common.SHAPE_END_CAP:
            w += arrow_width
            self._draw_width = w
            if self.get_direction() != gtk.TEXT_DIR_RTL:
                self._layout_points[0] += arrow_width

        elif shape == pathbar_common.SHAPE_MID_ARROW:
            w += arrow_width
            self._draw_width += 2*arrow_width
            if self.get_direction() == gtk.TEXT_DIR_RTL:
                self._draw_xoffset -= arrow_width
            else:
                self._layout_points[0] += arrow_width
        return w

    def _calc_size(self, shape):
        lx, ly, w, h = self.layout.get_pixel_extents()[1]
        w += 2*self._parent.theme['xpad']
        h += 2*self._parent.theme['ypad']

        self._draw_xoffset = 0
        self._draw_width = w
        w = self._adjust_width(shape, w)
        self._best_width = w
        self.set_size_request(w, h)
        return

    def do_callback(self):
        self.callback(self._parent, self)
        return

    def set_label(self, label):
        self.label = gobject.markup_escape_text(label.strip())
        if not self.layout:
            self._make_layout()
        else:
            self.layout.set_markup(self.label)
        self._calc_layout_points()
        self._calc_size(self.shape)
        self.queue_draw()
        return

    def set_shape(self, shape):
        self.shape = shape
        self._calc_layout_points()
        self._calc_size(shape)
        self.queue_draw()
        return

    def set_width(self, w):
        theme = self._parent.theme
        lw = w-theme['arrow_width']
        if self.shape == pathbar_common.SHAPE_MID_ARROW:
            lw -= theme['xpad']
        self.layout.set_width(lw*pango.SCALE)
        self._draw_width = w+theme['arrow_width']
        self.set_size_request(w, -1)
        return

    def get_draw_width(self):
        return self._draw_width

    def get_draw_xoffset(self):
        return self._draw_xoffset

    def get_best_width(self):
        return self._best_width

    def get_layout_points(self):
        return self._layout_points

    def get_layout(self):
        return self.layout


class NavigationBar(PathBar):

    APPEND_DELAY = 50

    def __init__(self, group=None):
        PathBar.__init__(self)
        self.set_size_request(-1, 28)
        self.id_to_part = {}
        return

    def add_with_id(self, label, callback, id, do_callback=True, animate=True):
        """
        Add a new button with the given label/callback

        If there is the same id already, replace the existing one
        with the new one
        """

        # check if we have the button of that id or need a new one
        if id in self.id_to_part:
            part = self.id_to_part[id]
            part.set_label(label)
        else:
            part = PathPart(parent=self, label=label, callback=callback)
            part.set_name(id)
#            part.id = id
            self.id_to_part[id] = part
            # check if animation should be used
#            if animate:
#                if do_callback:
#                    gobject.timeout_add(150, self.append, part)
#                else:
#                    gobject.timeout_add(150, self.append_no_callback, part)
#            else:
            gobject.timeout_add(self.APPEND_DELAY,
                                self.append,
                                part,
                                do_callback)
        return

    def remove_id(self, id):
        if not id in self.id_to_part:
            return
        part = self.id_to_part[id]
        del self.id_to_part[id]
        self.remove(part)
        return

    def remove_all(self, keep_first_part=True, do_callback=True):
        if len(self.get_parts()) <= 1: return
        root = self.get_children()[0]
        self.id_to_part = {root.get_name(): root}
        PathBar.remove_all(self, do_callback=do_callback)
        return

    def get_button_from_id(self, id):
        """
        return the button for the given id (or None)
        """
        if not id in self.id_to_part:
            return None
        return self.id_to_part[id]

    def get_label(self, id):
        """
        Return the label of the navigation button with the given id
        """
        if not id in self.id_to_part:
            return


#class Test:

#    def __init__(self):
#        self.counter = 0
#        w = gtk.Window()
#        w.connect("destroy", gtk.main_quit)
#        w.set_size_request(512, -1)
#        w.set_border_width(3)

#        vb = gtk.VBox()
#        w.add(vb)

#        pb = PathBar()
#        vb.pack_start(pb, False)
#        part = PathPart(pb, 'Get Free Software?')
#        pb.append(part)

#        add = gtk.Button(stock=gtk.STOCK_ADD)
#        rem = gtk.Button(stock=gtk.STOCK_REMOVE)
#        self.entry = gtk.Entry()

#        vb.pack_start(add, False)
#        vb.pack_start(self.entry, False)
#        vb.pack_start(rem, False)
#        add.connect('clicked', self.add_cb, pb)
#        rem.connect('clicked', self.rem_cb, pb)

#        w.show_all()
#        gtk.main()
#        return

#    def add_cb(self, widget, pb):
#        text = self.entry.get_text() or ('unnammed%s' % self.counter)
#        part = PathPart(pb, text)
#        pb.append(part)
#        self.counter += 1
#        return

#    def rem_cb(self, widget, pb):
#        last = pb.get_children()[-1]
#        pb.remove(last)
#        return

#Test()
