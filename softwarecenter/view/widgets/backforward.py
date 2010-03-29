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



import rgb
import gtk
import cairo
import gobject
import pathbar2

from rgb import to_float as f

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

        self.theme = self._pick_theme()
        self.connect("realize", self._on_realize)
        return

    def _pick_theme(self, name=None):
        name = name or gtk.settings_get_default().get_property("gtk-theme-name")
        themes = pathbar2.PathBarThemes.DICT
        if name in themes:
            return themes[name]()
        print "No styling hints for %s are available" % name
        return pathbar2.PathBarThemeHuman()

    def _on_realize(self, widget):
        self.theme.load(self.style)
        return


class SeparatorPart(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)
        self.set_size_request(1, -1)
        self.connect("expose-event", self._on_expose)
        return

    def _on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        a = event.area
        cr.rectangle(a.x, a.y+1, a.width, a.height-2)
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.fill()
        del cr
        return


class ButtonPart(gtk.DrawingArea):

    ARROW_SIZE = (12,12)
    DEFAULT_SIZE = (30, 28)

    def __init__(self, arrow_type, signal_name):
        gtk.DrawingArea.__init__(self)
        self.set_size_request(*self.DEFAULT_SIZE)
        self.button_down = False
        self.shadow_type = gtk.SHADOW_OUT
        self.arrow_type = arrow_type
        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK|
                        gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK)
        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release, signal_name)
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

#    def expose_gtk(self, widget, area, x, y, width, height):
#        # button background
#        widget.style.paint_box(widget.window,
#                               self.state,
#                               self.shadow_type,
#                               area,
#                               widget,
#                               "button",
#                               x,
#                               y,
#                               width,
#                               height)

#        # arrow
#        aw, ah = self.ARROW_SIZE
#        widget.style.paint_arrow(widget.window,
#                                 self.state,
#                                 self.shadow_type,
#                                 area,
#                                 widget,
#                                 "button",
#                                 self.arrow_type,
#                                 True,
#                                 (area.width - aw)/2,
#                                 (area.height - ah)/2,
#                                 aw,
#                                 ah)
#        return

    def expose_pathbar(self, widget, area, x, y, width, height):
        # background
        cr = widget.window.cairo_create()
        cr.rectangle(area)
        cr.clip()

        cr.translate(x, y)

        self._draw_bg(cr,
                      width,
                      height,
                      self.state,
                      self.style,
                      self.get_parent().theme,
                      self.get_parent().theme.curvature)
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
                                 (area.width - aw)/2,
                                 (area.height - ah)/2,
                                 aw,
                                 ah)
        return

    def _draw_bg(self, cr, w, h, state, style, theme, r):
        # outer slight bevel or focal highlight
        self._draw_rect(cr, 0, 0, w, h, r)
        cr.set_source_rgba(0, 0, 0, 0.055)
        cr.fill()
        
        # colour scheme dicts
        bg = theme.bg_colors
        outer = theme.dark_line_colors
        inner = theme.light_line_colors
        
        # bg linear vertical gradient
        if state != gtk.STATE_PRELIGHT:
            color1, color2 = bg[state]
        else:
            if self.state == gtk.STATE_ACTIVE:
                color1, color2 = bg[theme.PRELIT_NORMAL]
            else:
                color1, color2 = bg[theme.PRELIT_ACTIVE]

        self._draw_rect(cr, 1, 1, w-1, h-1, r)
        lin = cairo.LinearGradient(0, 0, 0, h-1)
        lin.add_color_stop_rgb(0.0, *color1)
        lin.add_color_stop_rgb(1.0, *color2)
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # strong outline
        self._draw_rect(cr, 1.5, 1.5, w-1.5, h-1.5, r)
        cr.set_source_rgb(*outer[state])
        cr.stroke()

        # inner bevel/highlight
        if theme.light_line_colors[state]:
            self._draw_rect(cr, 2.5, 2.5, w-2.5, h-2.5, r)
            r, g, b = inner[state]
            cr.set_source_rgba(r, g, b, 0.6)
            cr.stroke()
        return

    def _draw_rect(self, cr, x, y, w, h, r):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
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
                    area.x - 10,
                    area.y,
                    area.width + 10,
                    area.height)
        return
