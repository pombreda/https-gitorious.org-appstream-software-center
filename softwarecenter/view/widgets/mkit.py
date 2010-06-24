# mkit, a collection of handy things

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
import pango
import gobject

from mkit_themes import Color, ColorArray, ThemeRegistry

import logging

# todo phase out from here if possible
CAT_BUTTON_FIXED_WIDTH =    108
CAT_BUTTON_MIN_HEIGHT =     96
CAT_BUTTON_BORDER_WIDTH =   6
CAT_BUTTON_CORNER_RADIUS =  8


# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

# TODO: make metrics in terms of em
BORDER_WIDTH_LARGE =    10
BORDER_WIDTH_MED =      6
BORDER_WIDTH_SMALL =    3

VSPACING_XLARGE =       12
VSPACING_LARGE =        6    # vertical spacing between page elements
VSPACING_SMALL =        3

HSPACING_XLARGE =       12
HSPACING_LARGE =        6    # horizontal spacing between page elements
HSPACING_SMALL =        3

FRAME_CORNER_RADIUS =   3


# shapes
SHAPE_RECTANGLE = 0
SHAPE_START_ARROW = 1   
SHAPE_MID_ARROW = 2
SHAPE_END_CAP = 3
SHAPE_CIRCLE = 4



# color coversion functions
def color_from_gdkcolor(gdkcolor):
    return Color(gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float)

def color_from_string(spec):
    gdkcolor = gtk.gdk.color_parse(spec)
    return Color(gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float)

def floats_from_gdkcolor(gdkcolor):
    return gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float

def floats_from_gdkcolor_with_alpha(gdkcolor, a):
    r, g, b = floats_from_gdkcolor(gdkcolor)
    return r, g, b, a

def floats_from_string(spec):
    color = gtk.gdk.color_parse(spec)
    return color.red_float, color.green_float, color.blue_float

def floats_from_string_with_alpha(spec, a):
    r, g, b = floats_from_string(spec)
    return r, g, b, a

def not_overlapping(widget_area, expose_area):
    return gtk.gdk.region_rectangle(expose_area).rect_in(widget_area) == gtk.gdk.OVERLAP_RECTANGLE_OUT


class Shape:

    def __init__(self, direction):
        self.direction = direction
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        if self.direction != gtk.TEXT_DIR_RTL:
            self._layout_ltr(cr, x, y, w, h, *args, **kwargs)
        else:
            self._layout_rtl(cr, x, y, w, h, *args, **kwargs)
        return


class ShapeRoundedRectangle(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        self._layout_ltr(cr, x, y, w, h, *args, **kwargs)
        return


class ShapeRoundedRectangleIrregular(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        nw, ne, se, sw = kwargs['radii']

        cr.save()
        cr.translate(x, y)
        if nw:
            cr.new_sub_path()
            cr.arc(nw, nw, nw, M_PI, 270 * PI_OVER_180)
        else:
            cr.move_to(0, 0)
        if ne:
            cr.arc(w-ne, ne, ne, 270 * PI_OVER_180, 0)
        else:
            cr.rel_line_to(w-nw, 0)
        if se:
            cr.arc(w-se, h-se, se, 0, 90 * PI_OVER_180)
        else:
            cr.rel_line_to(0, h-ne)
        if sw:
            cr.arc(sw, h-sw, sw, 90 * PI_OVER_180, M_PI)
        else:
            cr.rel_line_to(-(w-se), 0)

        cr.close_path()
        cr.restore()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        self._layout_ltr(cr, x, y, w, h, *args, **kwargs)
        return


class ShapeStartArrow(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']
        r = kwargs['radius']

        cr.new_sub_path()
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(aw, h)
        cr.close_path()
        return


class ShapeMidArrow(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']

        cr.move_to(0, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.line_to(0, h)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']

        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.line_to(aw, h)
        cr.close_path()
        return


class ShapeEndCap(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.move_to(x, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(x, h)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return


class ShapeCircle(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        cr.new_path()

        r = max(w, h)*0.5
        x += int((w-2*r)/2)
        y += int((h-2*r)/2)

        cr.arc(r+x, r+y, r, 0, 360*PI_OVER_180)
        cr.close_path()
        return


class Style:

    def __init__(self, widget):
        self.shape_map = self._load_shape_map(widget)
        gtk_settings = gtk.settings_get_default()
        self.theme = self._load_theme(gtk_settings)
        self.theme.build_palette(gtk_settings)
        self.properties = self.theme.get_properties(gtk_settings)
        self.gradients = self.theme.get_grad_palette()
        self.dark_line = self.theme.get_dark_line_palette()
        self.light_line = self.theme.get_light_line_palette()
        self.text = self.theme.get_text_palette()
        self.text_states = self.theme.get_text_states()
        self.base_color = None
        return

    def __getitem__(self, item):
        if self.properties.has_key(item):
            return self.properties[item]
        logging.warn('Key does not exist in the style profile: %s' % item)
        return None

    def _load_shape_map(self, widget):
        if widget.get_direction() != gtk.TEXT_DIR_RTL:
            shmap = {SHAPE_RECTANGLE:   ShapeRoundedRectangle(gtk.TEXT_DIR_LTR),
                     SHAPE_START_ARROW: ShapeStartArrow(gtk.TEXT_DIR_LTR),
                     SHAPE_MID_ARROW:   ShapeMidArrow(gtk.TEXT_DIR_LTR),
                     SHAPE_END_CAP:     ShapeEndCap(gtk.TEXT_DIR_LTR),
                     SHAPE_CIRCLE :     ShapeCircle(gtk.TEXT_DIR_LTR)}
        else:
            shmap = {SHAPE_RECTANGLE:   ShapeRoundedRectangle(gtk.TEXT_DIR_RTL),
                     SHAPE_START_ARROW: ShapeStartArrow(gtk.TEXT_DIR_RTL),
                     SHAPE_MID_ARROW:   ShapeMidArrow(gtk.TEXT_DIR_RTL),
                     SHAPE_END_CAP:     ShapeEndCap(gtk.TEXT_DIR_RTL),
                     SHAPE_CIRCLE :     ShapeCircle(gtk.TEXT_DIR_RTL)}
        return shmap

    def _load_theme(self, gtksettings):
        name = gtksettings.get_property("gtk-theme-name")
        r = ThemeRegistry()
        return r.retrieve(name)

    def set_direction(self, direction):
        if direction != gtk.TEXT_DIR_RTL:
            shmap = {SHAPE_RECTANGLE:   ShapeRoundedRectangle(gtk.TEXT_DIR_LTR),
                     SHAPE_START_ARROW: ShapeStartArrow(gtk.TEXT_DIR_LTR),
                     SHAPE_MID_ARROW:   ShapeMidArrow(gtk.TEXT_DIR_LTR),
                     SHAPE_END_CAP:     ShapeEndCap(gtk.TEXT_DIR_LTR),
                     SHAPE_CIRCLE :     ShapeCircle(gtk.TEXT_DIR_LTR)}
        else:
            shmap = {SHAPE_RECTANGLE:   ShapeRoundedRectangle(gtk.TEXT_DIR_RTL),
                     SHAPE_START_ARROW: ShapeStartArrow(gtk.TEXT_DIR_RTL),
                     SHAPE_MID_ARROW:   ShapeMidArrow(gtk.TEXT_DIR_RTL),
                     SHAPE_END_CAP:     ShapeEndCap(gtk.TEXT_DIR_RTL),
                     SHAPE_CIRCLE :     ShapeCircle(gtk.TEXT_DIR_RTL)}
        self.shape_map = shmap
        return

    def paint_bg_flat(self, cr, part, x, y, w, h, r=None, sxO=0, alpha=1.0):
        shape = self.shape_map[part.shape]
        state = part.state
        r = r or self["curvature"]
        aw = self["arrow-width"]

        cr.save()

        cr.rectangle(x, y, w, h)
        cr.clip()
        cr.translate(x-sxO, y)

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        lin = cairo.LinearGradient(0, 0, 0, h)
        red, g, b = color1.floats()
        lin.add_color_stop_rgba(0.0, red, g, b, alpha)

        red, g, b = color2.floats()
        lin.add_color_stop_rgba(1.0, red, g, b, alpha)
        cr.set_source(lin)
        cr.fill()

        cr.restore()
        return

    def paint_bg(self, cr, part, x, y, w, h, r=None, sxO=0, alpha=1.0):
        shape = self.shape_map[part.shape]
        state = part.state
        r = r or self["curvature"]
        aw = self["arrow-width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)

        cr.clip()
        cr.translate(x-sxO, y)

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        lin = cairo.LinearGradient(0, 0, 0, h)
        red, g, b = color1.floats()
        lin.add_color_stop_rgba(0.0, red, g, b, alpha)

        red, g, b = color2.floats()
        lin.add_color_stop_rgba(1.0, red, g, b, alpha)
        cr.set_source(lin)
        cr.fill()

        cr.translate(0.5, 0.5)
        cr.set_line_width(1.0)

        w -= 1
        h -= 1

        # inner bevel/highlight
        shape.layout(cr, 1, 1, w-1, h-1, arrow_width=aw, radius=r-1)
        red, g, b = self.light_line[state].floats()
        cr.set_source_rgba(red, g, b, alpha)
        cr.stroke()

        # strong outline
        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        red, g, b = self.dark_line[state].floats()
        cr.set_source_rgba(red, g, b, alpha)
        cr.stroke()

        cr.restore()
        return

    def paint_bg_active_shallow(self, cr, part, x, y, w, h, sxO=0):
        shape = self.shape_map[part.shape]
        state = part.state
        r = self["curvature"]
        aw = self["arrow-width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5-sxO, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        cr.set_source_rgb(*color2.floats())
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow
        if r == 0: w += 1
        red, g, b = self.dark_line[state].floats()
        shape.layout(cr, 1, 1, w-0.5, h-1, arrow_width=aw, radius=r-1)
        cr.set_source_rgba(red, g, b, 0.3)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        cr.set_source_rgb(*self.dark_line[state].floats())
        cr.stroke()
        cr.restore()
        return

    def paint_bg_active_deep(self, cr, part, x, y, w, h, r=None):
        shape = self.shape_map[part.shape]
        state = part.state
        r = r or self["curvature"]
        aw = self["arrow-width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)

        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(2.0, *color1.floats())
        lin.add_color_stop_rgb(0.0, *color2.floats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow 1
        if r == 0: w += 1
        shape.layout(cr, 2, 2, w-2, h-2, arrow_width=aw, radius=r-2)
        red, g, b = self.dark_line[state].floats()
        cr.set_source_rgba(red, g, b, 0.1)
        cr.stroke()

        shape.layout(cr, 1, 1, w-1, h-1, arrow_width=aw, radius=r-1)
        cr.set_source_rgba(red, g, b, 0.4)
        cr.stroke()

        # strong outline
        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=r)
        cr.set_source_rgb(*self.dark_line[state].floats())
        cr.stroke()
        cr.restore()
        return

    def paint_layout(self, cr, widget, part, x, y, sxO=0):
        layout = part.get_layout()
        widget.style.paint_layout(widget.window,
                                  self.text_states[part.state],
                                  False,
                                  None,   # clip area
                                  widget,
                                  None,
                                  x, y,
                                  layout)
        return


class FramedSection(gtk.VBox):

    def __init__(self, label_markup=None):
        gtk.VBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_spacing(VSPACING_LARGE)

        self.header = gtk.HBox()
        self.body = gtk.VBox()

        self.header.set_border_width(BORDER_WIDTH_MED)
        self.body.set_border_width(BORDER_WIDTH_MED)
        self.body.set_spacing(VSPACING_SMALL)

        self.pack_start(self.header, False)
        self.pack_start(self.body)
        #self.pack_start(self.footer, False)

        self.label = gtk.Label()
        self.header.pack_start(self.label, False, padding=BORDER_WIDTH_SMALL)
        self.has_label = False

        if label_markup:
            self.set_label(label_markup)
        return

    def set_label(self, label):
        self.label.set_markup('<b>%s</b>' % label)
        self.has_label = True

        # atk stuff
        acc = self.get_accessible()
        acc.set_name(self.label.get_text())
        acc.set_role(atk.ROLE_SECTION)
        return

    def draw(self, cr, a, expose_area):
        if not_overlapping(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        # fill section white
        rr = ShapeRoundedRectangle()
        rr.layout(cr,
                  a.x+1, a.y+1,
                  a.x + a.width-2, a.y + a.height-2,
                  radius=FRAME_CORNER_RADIUS)


        cr.set_source_rgba(*floats_from_gdkcolor_with_alpha(self.style.light[gtk.STATE_NORMAL], 0.65))
        cr.fill()

        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        rr.layout(cr,
                  a.x+1, a.y+1,
                  a.x + a.width-2, a.y + a.height-2,
                  radius=FRAME_CORNER_RADIUS)

        cr.set_source_rgb(*floats_from_gdkcolor(self.style.dark[gtk.STATE_NORMAL]))
        cr.stroke_preserve()
        cr.stroke()
        cr.restore()

        cr.restore()
        return


class LayoutView(FramedSection):

    def __init__(self):
        FramedSection.__init__(self)
        self.set_redraw_on_allocate(False)

        self.column_hbox = gtk.HBox(spacing=HSPACING_SMALL)
        self.column_hbox.set_homogeneous(True)
        self.body.pack_start(self.column_hbox)

        self.widget_list = []
        self.theme = Style(self)
        return

    def append(self, widget):
        self.widget_list.append(widget)
        return

    def set_width(self, width):
        self.body.set_size_request(width, -1)

        # find widest button/widget
        widgets = self.widget_list
        widest_w = 0
        for btn in widgets:
            widest_w = max(widest_w, btn.calc_width())

        # determine number of columns to display
        width -= 100    # fudge number
        n_columns = width / widest_w
        n_columns = (width - n_columns*self.column_hbox.get_spacing()) / widest_w

        if n_columns > len(widgets):
            n_columns = len(widgets)

        # pack columns into widget
        for i in range(n_columns):
            self.column_hbox.pack_start(gtk.VBox(spacing=VSPACING_SMALL))

        # pack buttons into appropriate columns
        i = 0
        columns = self.column_hbox.get_children()
        for btn in widgets:
            columns[i].pack_start(btn, False)
            if i < n_columns-1:
                i += 1
            else:
                i = 0

        self.show_all()
        return

    def clear_all(self):
        self.widget_list = []
        for col in self.column_hbox.get_children():
            for child in col.get_children():
                child.destroy()
            col.destroy()
        return

    def clear_rows(self):
        for col in self.column_hbox.get_children():
            for btn in col.get_children():
                col.remove(btn)
            col.destroy()
        return

    def draw(self, cr, a, expose_area):
        if not_overlapping(a, expose_area): return

        cr.save()
        FramedSection.draw(self, cr, a, expose_area)

        for btn in self.widget_list:
            a = btn.allocation
            if a.width == 1 or a.height == 1: break

            btn.draw(cr, a, expose_area)

        cr.restore()
        return


class Button(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self, markup, icon_name, icon_size):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_redraw_on_allocate(False)

        self.label = gtk.Label()
        self.image = gtk.Image()

        if markup:
            self.label.set_markup(markup)
        if icon_name:
            self.image.set_from_icon_name(icon_name, icon_size)

        # atk stuff
        atk_obj = self.get_accessible()
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        # auto generated atk label
        atk_obj.set_name(self.label.get_text())

        self.shape = SHAPE_RECTANGLE
        self.theme = Style(self)

        self._relief = gtk.RELIEF_NORMAL
        self._has_action_arrow = False
        self._layout = None
        self._button_press_origin = None    # broken?
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)
        self._fixed_width = None

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.connect('realize', self._on_realize)
        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        return

    def _on_realize(self, widget):
        self.set_size_request(self.calc_width(), -1)
        #print self.allocation.width
        return

    def _on_enter(self, cat, event):
        if cat == self._button_press_origin:
            cat.set_state(gtk.STATE_ACTIVE)
        else:
            cat.set_state(gtk.STATE_PRELIGHT)

        self.window.set_cursor(self._cursor)
        return

    def _on_leave(self, cat, event):
        cat.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)
        return

    def _on_button_press(self, cat, event):
        if event.button != 1: return
        self._button_press_origin = cat
        cat.set_state(gtk.STATE_ACTIVE)
        return

    def _on_button_release(self, cat, event):
        if event.button != 1: return

        cat_region = gtk.gdk.region_rectangle(cat.allocation)
        if not cat_region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            return
        if cat != self._button_press_origin: return
        cat.set_state(gtk.STATE_PRELIGHT)
        self._button_press_origin = None
        self.emit('clicked')
        return

    def _on_key_press(self, cat, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            cat.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, cat, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            cat.set_state(gtk.STATE_NORMAL)
            self.emit('clicked')
        return

    def _draw_action_arrow(self, a, aw=10):  # d : arrow_width
        # draw arrow
        self.style.paint_arrow(self.window,
                               self.state,
                               gtk.SHADOW_NONE,
                               a,       #area
                               self,
                               None,
                               gtk.ARROW_RIGHT,
                               True,    # fill
                               a.x + a.width - aw - self.get_border_width(),
                               a.y + (a.height-aw)/2,
                               aw, aw)
        return

    def set_shape(self, shape):
        self.shape = shape
        return

    def set_relief(self, relief):
        self._relief = relief
        return

    def set_has_action_arrow(self, has_action_arrow):
        self._has_action_arrow = has_action_arrow
        return

    def draw(self, cr, a, expose_area, alpha=1.0):
        if not_overlapping(a, expose_area): return

        if self._relief == gtk.RELIEF_NORMAL:
            self.theme.paint_bg(cr, self, a.x, a.y, a.width-1, a.height, alpha=alpha)
            if self._has_action_arrow:
                self._draw_action_arrow(a)
        else:
            if self.state == gtk.STATE_PRELIGHT or \
                self.state == gtk.STATE_ACTIVE:
                self.theme.paint_bg(cr, self, a.x, a.y, a.width-1, a.height, alpha=alpha)
                if self._has_action_arrow:
                    self._draw_action_arrow(a)

        if self.has_focus():
            a = self.label.allocation
            x, y, w, h = a.x, a.y, a.width, a.height
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x-2, y-1, w+4, h+2),
                                   self,
                                   'button',
                                   x-2, y-1, w+4, h+2)
        return


#class VButton(Button):

    #def __init__(self, markup=None, icon_name=None, icon_size=gtk.ICON_SIZE_BUTTON):
        #Button.__init__(self, markup, icon_name, icon_size)

        #self.set_border_width(BORDER_WIDTH_MED)
        #self.label.set_line_wrap(gtk.WRAP_WORD)
        #self.label.set_justify(gtk.JUSTIFY_CENTER)

        ## determine size_request width for label
        #layout = self.label.get_layout()
        #layout.set_width(CAT_BUTTON_FIXED_WIDTH*pango.SCALE)
        #lw, lh = layout.get_pixel_extents()[1][2:]   # ink extents width, height
        #self.label.set_size_request(lw, -1)

        #self.vbox = gtk.VBox(spacing=VSPACING_SMALL)
        #h = lh + VSPACING_SMALL + 2*BORDER_WIDTH_MED + 48 # 32 = icon size
        #self.vbox.set_size_request(CAT_BUTTON_FIXED_WIDTH, max(h, CAT_BUTTON_MIN_HEIGHT))

        #self.add(self.vbox)
        #if self.image:
            #self.vbox.pack_start(self.image, False)

        #self.vbox.pack_start(self.label)
        #self.show_all()
        #return

    #def calc_width(self):
        #return CAT_BUTTON_FIXED_WIDTH + 2*self.get_border_width()

    #def draw(self, cr, a, expose_area):
        #if not_overlapping(a, expose_area): return

        #cr.save()
        #x, y, w, h = a.x, a.y, a.width, a.height
        #r = CAT_BUTTON_CORNER_RADIUS
        #if self.state == gtk.STATE_NORMAL:
            #pass
        #elif self.state != gtk.STATE_ACTIVE:
            #self.theme.paint_bg(cr, self, x, y, w, h, r)
        #else:
            #self.theme.paint_bg_active_deep(cr, self, x, y, w, h, r)

        #if self.has_focus():
            #self.style.paint_focus(self.window,
                                   #self.state,
                                   #(x+4, y+4, w-8, h-8),
                                   #self,
                                   #'button',
                                   #x+4, y+4, w-8, h-8)
        #cr.restore()
        #return


class HButton(Button):

    def __init__(self, markup=None, icon_name=None, icon_size=gtk.ICON_SIZE_BUTTON):
        Button.__init__(self, markup, icon_name, icon_size)

        hb = gtk.HBox()
        padding0 = gtk.HBox()
        padding1 = gtk.HBox()
        padding0.set_size_request(6, -1)
        padding1.set_size_request(6, -1)

        self.hbox = gtk.HBox()
        self.alignment = gtk.Alignment(0.5, 0.6) # left align margin
        self.alignment.add(self.hbox)

        self.add(hb)
        hb.pack_start(padding0, False)
        hb.pack_start(self.alignment)
        hb.pack_start(padding1, False)

        if not self.image.get_storage_type() == gtk.IMAGE_EMPTY:
            self.hbox.pack_start(self.image, False)
        if self.label.get_text():
            self.hbox.pack_start(self.label, False)

        self.set_border_width(BORDER_WIDTH_SMALL)
        self.show_all()
        return

    def calc_width(self):
        w = 1
        if self.label:
            pc = self.get_pango_context()
            layout = pango.Layout(pc)
            layout.set_markup(self.label.get_label())
            w += layout.get_pixel_extents()[1][2]
        if self.image and self.image.get_property('visible'):
            w += self.image.allocation.width

        w += 2*self.get_border_width() + 12 + self.hbox.get_spacing()
        return w

    def set_internal_xalignment(self, xalign):
        self.alignment.set(xalign,
                           self.alignment.get_property('yalign'),
                           0, 0)    # x/y scale
        return

    def set_internal_spacing(self, internal_spacing):
        self.hbox.set_spacing(internal_spacing)
        return

    def set_label(self, label):
        self.label.set_markup(label)
        return


class PlayPauseButton(Button):
    
    def __init__(self):
        Button.__init__(self, None, None, None)
        self.is_playing = True
        return

    def set_is_playing(self, is_playing):
        self.is_playing = is_playing
        return

    def calc_width(self):
        return self.allocation.width

    def draw(self, cr, a, expose_area, alpha=1.0):
        if not_overlapping(a, expose_area): return
        Button.draw(self, cr, a, expose_area, alpha)

        cr.save()

        r, g, b = self.theme.theme.text[self.state].floats()
        cr.set_source_rgba(r, g, b, 0.7)
        # if is_playing draw pause emblem
        if self.is_playing:
            w = max(2, int(a.width*0.2))
            h = max(6, int(a.height*0.55)) - 1
            gap = max(1, int(w/2))

            x = a.x + (a.width - 2*w + gap)/2-1
            y = a.y + (a.height - h)/2

            cr.rectangle(x, y, w, h)
            cr.fill()

            cr.rectangle(x+w+gap, y, w, h)
            cr.fill()

        # else, draw play emblem
        cr.restore()
        return
