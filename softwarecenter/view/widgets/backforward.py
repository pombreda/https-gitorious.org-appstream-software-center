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



import gtk
import cairo
import gobject
import pathbar_common

# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295


class BackForwardButton(gtk.HBox):

    __gsignals__ = {'left-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,)),

                    'right-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,))}

    def __init__(self):
        gtk.HBox.__init__(self)
        sep = SeparatorPart()

        if self.get_direction() != gtk.TEXT_DIR_RTL:
            self.left = ButtonPartLeft('left-clicked')
            self.right = ButtonPartRight('right-clicked')
        else:
            self.left = ButtonPartRight('left-clicked')
            self.right = ButtonPartLeft('right-clicked')

        self.pack_start(self.left)
        self.pack_start(sep, False)
        self.pack_end(self.right)
        return


class SeparatorPart(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.theme = pathbar_common.PathBarStyle(self.style)
        self.set_size_request(self.theme['xthickness'], -1)
        self.connect("expose-event", self._on_expose)
        return

    def _on_expose(self, widget, event):
        parent = self.get_parent()
        if not parent: return
        self.set_size_request(self.theme['xthickness'], -1)
        cr = widget.window.cairo_create()
        a = event.area
        cr.rectangle(a.x, a.y+1, a.width, a.height-1)
        dark = self.theme.dark_line[self.state]
        cr.set_source_rgba(*dark.tofloats())
        cr.fill()
        del cr
        return


class ButtonPart(gtk.DrawingArea):

    ARROW_SIZE = (12,12)
    DEFAULT_SIZE = (31, 29)

    def __init__(self, arrow_type, signal_name):
        gtk.DrawingArea.__init__(self)
        self.set_size_request(*self.DEFAULT_SIZE)
        self.shape = pathbar_common.SHAPE_RECTANGLE
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        self.arrow_type = arrow_type
        self.theme = pathbar_common.PathBarStyle(self.style)
        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK|
                        gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release, signal_name)
        self.connect("style-set", self._on_style_set)
        return

    def set_sensitive(self, is_sensitive):
        if is_sensitive:
            self.set_state(gtk.STATE_NORMAL)
        super(ButtonPart, self).set_sensitive(is_sensitive)
        return

    def set_active(self, is_active):
        if is_active:
            self.shadow_type = gtk.SHADOW_IN
            self.set_state(gtk.STATE_ACTIVE)
        else:
            self.shadow_type = gtk.SHADOW_OUT
            self.set_state(gtk.STATE_NORMAL)
        return

    def _on_enter(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        if not self.button_down:
            self.set_state(gtk.STATE_PRELIGHT)
        else:
            self.set_active(True)
        return

    def _on_leave(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.set_active(False)
        return

    def _on_press(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.button_down = True
        self.set_active(True)
        return

    def _on_release(self, widget, event, signal_name):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        p = gtk.gdk.device_get_core_pointer()
        x, y = p.get_state(widget.window)[0]
        rr = gtk.gdk.region_rectangle(widget.allocation)
        if rr.point_in(int(x+widget.allocation.x), int(y+widget.allocation.y)):
            self.set_state(gtk.STATE_PRELIGHT)
            self.get_parent().emit(signal_name, event)
        else:
            self.set_state(gtk.STATE_NORMAL)
        return

    def _on_style_set(self, widget, oldstyle):
        # when alloc.width == 1, this is typical of an unallocated widget,
        # lets not break a sweat for nothing...
        if self.allocation.width == 1:
            return

        self.theme = pathbar_common.PathBarStyle(self.style)
        self.queue_draw()
        return

    def expose_pathbar(self, widget, area, x, y, w, h):
        # background
        cr = widget.window.cairo_create()
        cr.rectangle(area)
        cr.clip()

        self.theme.draw_part_bg_ltr(cr,
                                    self,
                                    x, y, w, h)
        del cr

        # arrow
        aw, ah = self.ARROW_SIZE
        widget.style.paint_arrow(widget.window,
                                 self.state,
                                 self.shadow_type,
                                 area,
                                 widget,
                                 "button",
                                 self.arrow_type,
                                 True,
                                 int((area.width-1 - aw)*0.5+0.5),
                                 int((area.height - ah)*0.5+0.5),
                                 aw,
                                 ah)
        return


class ButtonPartLeft(ButtonPart):

    def __init__(self, sig_name):
        ButtonPart.__init__(self, gtk.ARROW_LEFT, sig_name)
        self.connect("expose-event", self._on_expose, self.expose_pathbar)
        return

    def _on_expose(self, widget, event, expose_func):
        area = event.area
        expose_func(widget,
                    area,
                    area.x,
                    area.y,
                    area.width + 10,
                    area.height)
        return


class ButtonPartRight(ButtonPart):

    def __init__(self, sig_name):
        ButtonPart.__init__(self, gtk.ARROW_RIGHT, sig_name)
        self.connect("expose-event", self._on_expose, self.expose_pathbar)
        return

    def _on_expose(self, widget, event, expose_func):
        area = event.area
        expose_func(widget,
                    area,
                    area.x-10,
                    area.y,
                    area.width+10,
                    area.height)
        return
