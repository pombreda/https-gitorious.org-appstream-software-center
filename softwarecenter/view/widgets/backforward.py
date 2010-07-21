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
import gtk
import cairo
import gobject
import mkit

from gettext import gettext as _


DEFAULT_PART_SIZE = (29, -1)
DEFAULT_ARROW_SIZE = (12, 12)


class BackForwardButton(gtk.HBox):

    __gsignals__ = {'left-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,)),

                    'right-clicked':(gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE,
                                    (gtk.gdk.Event,))}

    def __init__(self, part_size=None, arrow_size=None, native_draw=True):
        gtk.HBox.__init__(self)
        self.theme = mkit.get_mkit_theme()
        self.separator = SeparatorPart()

        self.use_hand = False
        self._use_flat_palatte = False

        part_size = part_size or DEFAULT_PART_SIZE
        arrow_size = arrow_size or DEFAULT_ARROW_SIZE

        if self.get_direction() != gtk.TEXT_DIR_RTL:
            # ltr
            self.left = ButtonPartLeft('left-clicked', part_size, arrow_size)
            self.right = ButtonPartRight('right-clicked', part_size, arrow_size)
            self.set_button_atk_info_ltr()
        else:
            # rtl
            self.left = ButtonPartRight('left-clicked', part_size, arrow_size)
            self.right = ButtonPartLeft('right-clicked', part_size, arrow_size)
            self.set_button_atk_info_rtl()

        atk_obj = self.get_accessible()
        atk_obj.set_name(_('History Navigation'))
        atk_obj.set_description(_('Navigate forwards and backwards.'))
        atk_obj.set_role(atk.ROLE_PANEL)

        self.pack_start(self.left)
        self.pack_start(self.separator, False)
        self.pack_end(self.right)

        self.separator.connect_after("style-set", self._on_style_set)
        self.connect_after('size-allocate', self._on_size_allocate)

        if not native_draw:
            self.set_redraw_on_allocate(False)
            self.connect('expose-event', lambda w, e: True)
        return

    def set_button_atk_info_ltr(self):
        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        return

    def set_button_atk_info_rtl(self):
        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        return

    def set_use_hand_cursor(self, use_hand):
        self.use_hand = use_hand
        return

    def _on_style_set(self, widget, oldstyle):
        # when alloc.width == 1, this is typical of an unallocated widget,
        # lets not break a sweat for nothing...
        if self.allocation.width == 1:
            return

        old_xthickness = self.theme['xthickness']
        self.theme = mkit.get_mkit_theme()
        if old_xthickness > self.theme['xthickness']:
            a = self.allocation
            self.queue_draw_area(a.x, a.y,
                                 a.width+self.theme['xthickness'], a.height)
        else:
            self.queue_draw()
        return

    def _on_size_allocate(self, widget, allocation):
        self.queue_draw()
        return

    def draw(self, cr, expose_area, left_alpha=1.0, right_alpha=1.0):
        self.separator.alpha = max(left_alpha, right_alpha)
        self.separator.queue_draw()
        self.left.draw(cr, expose_area, left_alpha)
        self.right.draw(cr, expose_area, right_alpha)
        return


class SeparatorPart(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.alpha = 1.0
        self.theme = mkit.get_mkit_theme()
        self.set_size_request(self.theme['xthickness'], -1)

        atk_obj = self.get_accessible()
        atk_obj.set_role(atk.ROLE_SEPARATOR)

        self.connect("expose-event", self._on_expose)
        self.connect("style-set", self._on_style_set)
        return

    def _on_expose(self, widget, event):
        parent = self.get_parent()
        if not parent: return
        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        if self.alpha == 1.0:
            cr.set_source_rgb(*self.theme.dark_line[self.state].floats())
        else:
            r, g, b = self.theme.dark_line[self.state].floats()
            cr.set_source_rgba(r, g, b, self.alpha)

        cr.fill()
        del cr
        return

    def _on_style_set(self, widget, old_style):
        self.theme = mkit.get_mkit_theme()
        self.set_size_request(self.theme['xthickness'], -1)
        return


class ButtonPart(gtk.EventBox):

    def __init__(self, arrow_type, signal_name, part_size, arrow_size):
        gtk.EventBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_visible_window(False)

        self.set_size_request(*part_size)
        self.shape = mkit.SHAPE_RECTANGLE
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        self.arrow_type = arrow_type
        self.arrow_size = arrow_size

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK|
                        gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK)

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release, signal_name)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release, signal_name)
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
        if self.parent.use_hand:
            self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, widget, event, signal_name):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self.set_state(gtk.STATE_SELECTED)
            self.get_parent().emit(signal_name, event)
        return

    def _on_leave(self, widget, event):
        if self.state == gtk.STATE_INSENSITIVE: return
        self.set_active(False)
        if self.parent.use_hand:
            self.window.set_cursor(None)
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
        if rr.point_in(int(x), int(y)):
            self.set_state(gtk.STATE_PRELIGHT)
            self.get_parent().emit(signal_name, event)
        else:
            self.set_state(gtk.STATE_NORMAL)
        return

    def do_draw(self, cr, a, expose_area, xo, wo, alpha):
        if gtk.gdk.region_rectangle(expose_area).rect_in(a) == gtk.gdk.OVERLAP_RECTANGLE_OUT:
            return
        if not self.parent.get_property('visible'): return

        cr.save()
        cr.rectangle(a)
        cr.clip()


        if not self.parent._use_flat_palatte:            
            self.parent.theme.paint_bg(cr,
                                       self,
                                       a.x+xo, a.y,
                                       a.width+wo, a.height,
                                       alpha=alpha)
        else:
            self.parent.theme.paint_bg_flat(cr,
                                            self,
                                            a.x+xo, a.y,
                                            a.width+wo, a.height,
                                            alpha=alpha)

        if self.has_focus():
            self.style.paint_focus(self.window,
                                   self.state,
                                   (a.x+4, a.y+4, a.width-8, a.height-8),
                                   self,
                                   'button',
                                   a.x+4, a.y+4,
                                   a.width-8, a.height-8)

        # arrow
        aw = ah = 12
        ay = a.y + (a.height - ah)/2
        ax = a.x + (a.width - aw)/2

        self.style.paint_arrow(self.window,
                               self.state,
                               self.shadow_type,
                               (ax, ay, aw, ah),
                               self,
                               None,
                               self.arrow_type,
                               True,
                               ax, ay,
                               aw, ah)
        cr.restore()
        return


class ButtonPartLeft(ButtonPart):

    def __init__(self, sig_name, part_size, arrow_size):
        ButtonPart.__init__(self,
                            gtk.ARROW_LEFT,
                            sig_name,
                            part_size,
                            arrow_size)
        self.connect("expose-event", self._on_expose)
        return

    def _on_expose(self, widget, event):
        cr = self.window.cairo_create()
        a = self.allocation
        self.draw(cr, event.area, alpha=1.0)
        return

    def draw(self, cr, expose_area, alpha):
        r = int(self.parent.theme['curvature'])
        self.do_draw(cr,
                     self.allocation,
                     expose_area,
                     xo=0,
                     wo=r,
                     alpha=alpha)
        return


class ButtonPartRight(ButtonPart):

    def __init__(self, sig_name, part_size, arrow_size):
        ButtonPart.__init__(self,
                            gtk.ARROW_RIGHT,
                            sig_name,
                            part_size,
                            arrow_size)
        self.connect("expose-event", self._on_expose)
        return

    def _on_expose(self, widget, event):
        cr = self.window.cairo_create()
        self.draw(cr, event.area, alpha=1.0)
        return

    def draw(self, cr, expose_area, alpha):
        r = int(self.parent.theme['curvature'])
        self.do_draw(cr,
                     self.allocation,
                     expose_area,
                     xo=-r,
                     wo=r,
                     alpha=alpha)
        return
