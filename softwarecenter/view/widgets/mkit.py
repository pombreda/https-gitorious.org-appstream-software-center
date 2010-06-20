# mkit, a collection of handy thing

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

# todo pahase out from here if possible
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

# common shapes
def rounded_rectangle(cr, x, y, w, h, r):
    cr.save()
    cr.translate(x, y)
    cr.new_sub_path()
    cr.arc(r, r, r, M_PI, 270*PI_OVER_180)
    cr.arc(w-r, r, r, 270*PI_OVER_180, 0)
    cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
    cr.arc(r, h-r, r, 90*PI_OVER_180, M_PI)
    cr.close_path()
    cr.restore()
    return

def rounded_rectangle_irregular(cr, x, y, w, h, corner_radii):
    nw, ne, se, sw = corner_radii
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

def is_overlapping(widget_area, expose_area):
    return gtk.gdk.region_rectangle(expose_area).rect_in(widget_area) == gtk.gdk.OVERLAP_RECTANGLE_OUT


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
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_ltr,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_ltr,
                     SHAPE_END_CAP:     self._shape_end_cap_ltr,
                     SHAPE_CIRCLE :     self._shape_circle}
        else:
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_rtl,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_rtl,
                     SHAPE_END_CAP:     self._shape_end_cap_rtl,
                     SHAPE_CIRCLE :     self._shape_circle}
        return shmap

    def _load_theme(self, gtksettings):
        name = gtksettings.get_property("gtk-theme-name")
        r = ThemeRegistry()
        return r.retrieve(name)

    def _shape_rectangle(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_circle(self, cr, x, y, w, h, r=None, aw=None):
        global M_PI, PI_OVER_180
        cr.new_path()
        r = min(w/2, h/2)
        cr.arc(r+x, r+y, r, 0, 360*PI_OVER_180)
        cr.close_path()
        return

    def _shape_start_arrow_ltr(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_mid_arrow_ltr(self, cr, x, y, w, h, r, aw):
        cr.move_to(0, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.line_to(0, h)
        cr.close_path()
        return

    def _shape_end_cap_ltr(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.move_to(x, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(x, h)
        cr.close_path()
        return

    def _shape_start_arrow_rtl(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_mid_arrow_rtl(self, cr, x, y, w, h, r, aw):
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_end_cap_rtl(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def set_direction(self, direction):
        if direction != gtk.TEXT_DIR_RTL:
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_ltr,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_ltr,
                     SHAPE_END_CAP:     self._shape_end_cap_ltr,
                     SHAPE_CIRCLE :     self._shape_circle,
                     }
        else:
            shmap = {SHAPE_RECTANGLE:   self._shape_rectangle,
                     SHAPE_START_ARROW: self._shape_start_arrow_rtl,
                     SHAPE_MID_ARROW:   self._shape_mid_arrow_rtl,
                     SHAPE_END_CAP:     self._shape_end_cap_rtl,
                     SHAPE_CIRCLE :     self._shape_circle,
                     }
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

        shape(cr, 0, 0, w, h, r, aw)
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

        shape(cr, 0, 0, w, h, r, aw)
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
        shape(cr, 1, 1, w-1, h-1, r-1, aw)
        red, g, b = self.light_line[state].floats()
        cr.set_source_rgba(red, g, b, alpha)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r, aw)
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

        shape(cr, 0, 0, w, h, r, aw)
        cr.set_source_rgb(*color2.floats())
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow
        if r == 0: w += 1
        red, g, b = self.dark_line[state].floats()
        shape(cr, 1, 1, w-0.5, h-1, r-1, aw)
        cr.set_source_rgba(red, g, b, 0.3)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r, aw)
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

        shape(cr, 0, 0, w, h, r, aw)

        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(2.0, *color1.floats())
        lin.add_color_stop_rgb(0.0, *color2.floats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow 1
        if r == 0: w += 1
        shape(cr, 2, 2, w-2, h-2, r-2, aw)
        red, g, b = self.dark_line[state].floats()
        cr.set_source_rgba(red, g, b, 0.1)
        cr.stroke()

        shape(cr, 1, 1, w-1, h-1, r-1, aw)
        cr.set_source_rgba(red, g, b, 0.4)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r, aw)
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

        align = gtk.Alignment(0.5, 0.5)
        align.add(self.body)

        self.pack_start(self.header, False)
        self.pack_start(align)
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
        if is_overlapping(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        # fill section white
        rounded_rectangle(cr, a.x+1, a.y+1, a.width-2, a.height-2, FRAME_CORNER_RADIUS)
        cr.set_source_rgba(*floats_from_gdkcolor_with_alpha(self.style.light[gtk.STATE_NORMAL], 0.65))
        cr.fill()

        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        rounded_rectangle(cr, a.x+1, a.y+1, a.width-2, a.height-2, FRAME_CORNER_RADIUS)
        cr.set_source_rgb(*floats_from_gdkcolor(self.style.dark[gtk.STATE_NORMAL]))
        cr.stroke_preserve()
        cr.stroke()
        cr.restore()

        ## header gradient - suppose to be ubuntu wallpaper-esque
        #pink = '#FCE3DD'
        #h = 48
        #r, g, b = floats_from_string(pink)
        ##r, g, b = floats_from_color(self.style.mid[gtk.STATE_NORMAL])
        #lin = cairo.LinearGradient(0, a.y+1, 0, a.y+h)
        #lin = cairo.LinearGradient(0, a.y+1, 0, a.y+h)
        #lin.add_color_stop_rgba(0.0, r, g, b, 0.8)
        #lin.add_color_stop_rgba(1.0, r, g, b, 0)
        #rounded_rectangle(cr, a.x+2, a.y+2, a.width-3, a.height-3, FRAME_CORNER_RADIUS-1)
        #cr.set_source(lin)
        #cr.fill()

        cr.restore()
        return


class LayoutView(FramedSection):

    def __init__(self):

        FramedSection.__init__(self)
        self.hspacing = HSPACING_SMALL

        self.set_redraw_on_allocate(False)
        self.widget_list = []

        self.theme = Style(self)
        self._prev_width = 0
        return

    def _on_allocate(self, widget, allocation):
        if self._prev_width == allocation.width: return
        self._prev_width = allocation.width
        self._clear_rows()
        self.set_width()
        return

    def append(self, widget):
        self.widget_list.append(widget)
        return

    def set_width(self, width):
        row = LayoutRow(self.hspacing)
        self.body.pack_start(row, False)

        spacing = self.hspacing
        width -= 3*BORDER_WIDTH_MED
        w = 0

        for cat in self.widget_list:
            cw = cat.calc_width(self)

            if w + cw + spacing <= width:
                row.pack_start(cat, False)
                w += cw + spacing
            else:
                row = LayoutRow(self.hspacing)
                self.body.pack_start(row, False)
                row.pack_start(cat, False)
                w = cw + spacing

        self.show_all()
        return

    def clear_all(self):
        self.widget_list = []
        for row in self.body.get_children():
            for child in row.get_children():
                child.destroy()
            row.destroy()
        return

    def clear_rows(self):
        for row in self.body.get_children():
            for cat in row.hbox.get_children():
                row.hbox.remove(cat)
            row.destroy()
        return

    def draw(self, cr, a, expose_area):
        if is_overlapping(a, expose_area): return

        cr.save()
        FramedSection.draw(self, cr, a, expose_area)

        for cat in self.widget_list:
            a = cat.allocation
            if a.width == 1 or a.height == 1: break
            cat.draw(cr, a, expose_area, self.theme)

        cr.restore()
        return


class LayoutRow(gtk.Alignment):

    def __init__(self, hspacing):
        gtk.Alignment.__init__(self, 0.5, 0.5)
        self.hbox = gtk.HBox(spacing=hspacing)
        self.set_redraw_on_allocate(False)
        self.hbox.set_redraw_on_allocate(False)
        self.add(self.hbox)
        return

    def __getitem__(self, index):
        return self.hbox.get_children()[index]

    def pack_start(self, cat, *args, **kwargs):
        self.hbox.pack_start(cat, *args, **kwargs)
        return

    def pack_end(self, cat, *args, **kwargs):
        self.hbox.pack_end(cat, *args, **kwargs)
        return


class Button(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self, markup, image=None):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_redraw_on_allocate(False)

        self.markup = markup
        self.label = gtk.Label()
        self.label.set_markup(markup)
        self.image = image
        self.shape = SHAPE_RECTANGLE
        self.theme = Style(self)

        # atk stuff
        atk_obj = self.get_accessible()
        atk_obj.set_name(self.label.get_text())
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        self._layout = None
        self._button_press_origin = None    # broken?
        #self._use_flat_palatte = True
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
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

    def draw(self, cr, a, expose_area, alpha=1.0):
        if is_overlapping(a, expose_area): return

        self.theme.paint_bg(cr, self, a.x, a.y, a.width-1, a.height, alpha=alpha)

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


class VButton(Button):

    def __init__(self, markup, image=None):
        Button.__init__(self, markup, image)
        self.set_border_width(BORDER_WIDTH_MED)
        self.label.set_line_wrap(gtk.WRAP_WORD)
        self.label.set_justify(gtk.JUSTIFY_CENTER)

        # determine size_request width for label
        layout = self.label.get_layout()
        layout.set_width(CAT_BUTTON_FIXED_WIDTH*pango.SCALE)
        lw, lh = layout.get_pixel_extents()[1][2:]   # ink extents width, height
        self.label.set_size_request(lw, -1)

        self.vbox = gtk.VBox(spacing=VSPACING_SMALL)
        h = lh + VSPACING_SMALL + 2*BORDER_WIDTH_MED + 48 # 32 = icon size
        self.vbox.set_size_request(CAT_BUTTON_FIXED_WIDTH, max(h, CAT_BUTTON_MIN_HEIGHT))

        self.add(self.vbox)
        if self.image:
            self.vbox.pack_start(self.image, False)

        self.vbox.pack_start(self.label)
        self.show_all()
        return

    def calc_width(self, realized_widget):
        return CAT_BUTTON_FIXED_WIDTH + 2*self.get_border_width()

    def draw(self, cr, a, expose_area, theme):
        if is_overlapping(a, expose_area): return

        cr.save()
        x, y, w, h = a.x, a.y, a.width, a.height
        r = CAT_BUTTON_CORNER_RADIUS
        if self.state == gtk.STATE_NORMAL:
            pass
        elif self.state != gtk.STATE_ACTIVE:
            theme.paint_bg(cr, self, x, y, w, h, r)
        else:
            theme.paint_bg_active_deep(cr, self, x, y, w, h, r)

        if self.has_focus():
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x+4, y+4, w-8, h-8),
                                   self,
                                   'button',
                                   x+4, y+4, w-8, h-8)
        cr.restore()
        return


class HButton(Button):

    def __init__(self, markup):
        Button.__init__(self, markup, image=None)
        self.set_border_width(BORDER_WIDTH_SMALL)
        self.alignment = gtk.Alignment(0.5, 0.5)
        self.alignment.add(self.label)
        self.add(self.alignment)
        self.show_all()

        self.connect('realize', self._on_realize)
        return

    def _on_realize(self, widget):
        self.set_size_request(self.calc_width(), -1)
        print self.allocation
        return

    def calc_width(self):
        pc = self.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.label.get_label())
        lw = layout.get_pixel_extents()[1][2]
        return lw + 12 + self.get_border_width()

    def set_border_width(self, width):
        gtk.EventBox.set_border_width(self, width)
        self.set_size_request(self.calc_width(), -1)
        return

    def set_label(self, label):
        self.label.set_markup(label)
        self.set_size_request(self.calc_width(), -1)
        return
