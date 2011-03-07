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
import pangocairo
from math import pi, cos, sin

from math import sin, cos

from mkit_themes import Color, ColorArray, ThemeRegistry

import logging


#######################
### HANDY FUNCTIONS ###
#######################

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

def get_gtk_color_scheme_dict():
    # Color names as provided by gtk.Settings:
    # Note: Not all Gtk themes support this method of color retrieval!

    # 'tooltip_fg_color'
    # 'fg_color'
    # 'base_color'
    # 'selected_bg_color'
    # 'selected_fg_color'
    # 'text_color'
    # 'bg_color'
    # 'tooltip_bg_color'

    scheme_str = gtk.settings_get_default().get_property("gtk-color-scheme")
    d = {}
    lines = scheme_str.splitlines()
    if not lines: return

    for ln in lines:
        try:
            k, v = ln.split(':')
            d[k.strip()] = v.strip()
        except:
            pass
    return d

def get_em_value():
    # calc the width of a wide character, use as 1em
    w = gtk.Window()
    pc = w.get_pango_context()
    l = pango.Layout(pc)
    # 'M' is wide
    l.set_markup('M')
    return l.get_pixel_extents()[1][2]

def get_nearest_stock_size(desired_size):
    stock_sizes = (16, 24, 32, 48, 64, 84)
    desired_to_stock_ratios = []

    # first divide the desired icon size by each of the stock sizes
    for size in stock_sizes:
        desired_to_stock_ratios.append(desired_size / float(size))

    # then choose the stock size whose desired_to_stock ratio is nearest to 1
    best_ratio = 1
    best_size = 0
    for i, ratio in enumerate(desired_to_stock_ratios):
        proximity_to_one = abs(1 - ratio)
        if proximity_to_one < best_ratio:
            best_size = stock_sizes[i]
            best_ratio = proximity_to_one

    return best_size

def not_overlapping(widget_area, expose_area):
    return gtk.gdk.region_rectangle(expose_area).rect_in(widget_area) == gtk.gdk.OVERLAP_RECTANGLE_OUT



#######################
### HANDY CONSTANTS ###
#######################

# pi constants
PI =            pi
PI_OVER_180 =   pi / 180

# shapes constants
SHAPE_RECTANGLE =   0
SHAPE_START_ARROW = 1   
SHAPE_MID_ARROW =   2
SHAPE_END_CAP =     3
SHAPE_CIRCLE =      4

# active paint modes
ACTIVE_PAINT_MODE_NORMAL =  0
ACTIVE_PAINT_MODE_DEEP =    1

# the em value
EM = get_em_value()

# recommended border metrics (integers)
BORDER_WIDTH_XLARGE = max(5, int(1.333*EM+0.5))  
BORDER_WIDTH_LARGE =    max(3, EM)
BORDER_WIDTH_MED =      max(2, int(0.666*EM+0.5))
BORDER_WIDTH_SMALL =    max(1, int(0.333*EM+0.5))

# recommended spacings between elements
SPACING_XLARGE      = max(5, int(1.333*EM+0.5))    
SPACING_LARGE       = max(3, EM)
SPACING_MED         = max(2, int(0.666*EM+0.5))
SPACING_SMALL       = max(1, int(0.333*EM+0.5))

# recommended corner radius
CORNER_RADIUS = 0
LINK_ACTIVE_COLOR = '#FF0000'   # red



# DEBUGGING
#print '\n* MKIT METRICS'
#print '1EM:', EM
#print 'BORDER_WIDTH_L:',BORDER_WIDTH_LARGE
#print 'BORDER_WIDTH_M:',BORDER_WIDTH_MED
#print 'BORDER_WIDTH_S:', BORDER_WIDTH_SMALL

#print 'SPACING_L:', SPACING_LARGE
#print 'SPACING_M:', SPACING_MED
#print 'SPACING_S:', SPACING_SMALL

#print 'CORNER_R:', CORNER_RADIUS



##############################
### ANOTHER HANDY FUNCTION ###
##############################

def update_em_metrics():
    # if the gtk-font-name changes, this can be called to update
    # all em dependent metrics
    global EM
    if EM == get_em_value(): return
    EM = get_em_value()

    global BORDER_WIDTH_LARGE, BORDER_WIDTH_MED, BORDER_WIDTH_SMALL
    BORDER_WIDTH_LARGE =    max(3, EM)
    BORDER_WIDTH_MED =      max(2, int(0.666*EM+0.5))
    BORDER_WIDTH_SMALL =    max(1, int(0.333*EM+0.5))

    # recommended spacings between elements
    global SPACING_LARGE, SPACING_MED, SPACING_SMALL
    SPACING_LARGE =         max(3, EM)
    SPACING_MED =           max(2, int(0.666*EM+0.5))
    SPACING_SMALL =         max(1, int(0.333*EM+0.5))

    # recommended corner radius
    global CORNER_RADIUS
    CORNER_RADIUS =         max(2, int(0.333*EM+0.5))


    # DEBUGGING
    #print '\n* METRICS'
    #print '1EM:', EM
    #print 'BORDER_WIDTH_L:',BORDER_WIDTH_LARGE
    #print 'BORDER_WIDTH_M:',BORDER_WIDTH_MED
    #print 'BORDER_WIDTH_S:', BORDER_WIDTH_SMALL

    #print 'SPACING_L:', SPACING_LARGE
    #print 'SPACING_M:', SPACING_MED
    #print 'SPACING_S:', SPACING_SMALL

    #print 'CORNER_R:', CORNER_RADIUS
    return



# cache theme as much as possible to help speed things up
CACHED_THEME = None
CACHED_THEME_NAME = None

def get_mkit_theme():
    global CACHED_THEME, CACHED_THEME_NAME

    name = gtk.settings_get_default().get_property("gtk-theme-name")

    if name != CACHED_THEME_NAME or not CACHED_THEME:
        CACHED_THEME = Style()
        CACHED_THEME_NAME = name
        return CACHED_THEME

    return CACHED_THEME

def radian(deg):
    return PI_OVER_180 * deg



#####################
### HANDY CLASSES ###
#####################


class Shape:

    """ Base class for a Shape implementation.

        Currently implements a single method <layout> which is called
        to layout the shape using cairo paths.  It can also store the
        'direction' of the shape which should be on of the gtk.TEXT_DIR
        constants.  Default 'direction' is gtk.TEXT_DIR_LTR.

        When implementing a Shape, there are two options available.

        If the Shape is direction dependent, the Shape MUST
        implement <_layout_ltr> and <_layout_rtl> methods.
        
        If the Shape is not direction dependent, then it simply can
        override the <layout> method.

        <layout> methods must take the following as arguments:

        cr :    a CairoContext
        x  :    x coordinate
        y  :    y coordinate
        w  :    width value
        h  :    height value

        <layout> methods can then be passed Shape specific
        keyword arguments which can be used as draw-time modifiers.
    """

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

    """
        RoundedRectangle lays out a rectangle with all four corners
        rounded as specified at the layout call by the keyword argument:

        radius :    an integer or float specifying the corner radius.
                    The radius must be > 0.

        RoundedRectangle is not direction sensitive.
    """

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
        cr.close_path()
        return


class ShapeRoundedRectangleIrregular(Shape):

    """
        RoundedRectangleIrregular lays out a rectangle for which each
        individual corner can be rounded by a specific radius,
        as specified at the layout call by the keyword argument:

        radii : a 4-tuple of ints or floats specifying the radius for
                each corner.  A value of 0 is acceptable as a radius, it
                will result in a squared corner.

        RoundedRectangleIrregular is not direction sensitive.
    """

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        nw, ne, se, sw = kwargs['radii']

        cr.save()
        cr.translate(x, y)
        if nw:
            cr.new_sub_path()
            cr.arc(nw, nw, nw, PI, 270 * PI_OVER_180)
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
            cr.arc(sw, h-sw, sw, 90 * PI_OVER_180, PI)
        else:
            cr.rel_line_to(-(w-se), 0)

        cr.close_path()
        cr.restore()
        return


class ShapeStartArrow(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def _layout_ltr(self, cr, x, y, w, h, *args, **kwargs):
        aw = kwargs['arrow_width']
        r = kwargs['radius']

        cr.new_sub_path()
        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
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

        cr.move_to(x, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w-x+1, (h+y)/2)
        cr.line_to(w-aw, h)
        cr.line_to(x, h)
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
        aw = kwargs['arrow_width']

        cr.move_to(x-1, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(x-1, h)
        cr.line_to(x+aw, (h+y)/2)
        cr.close_path()
        return

    def _layout_rtl(self, cr, x, y, w, h, *args, **kwargs):
        r = kwargs['radius']

        cr.arc(r+x, r+y, r, PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, PI)
        cr.close_path()
        return


class ShapeCircle(Shape):

    def __init__(self, direction=gtk.TEXT_DIR_LTR):
        Shape.__init__(self, direction)
        return

    def layout(self, cr, x, y, w, h, *args, **kwargs):
        cr.new_path()

        r = min(w, h)*0.5
        x += int((w-2*r)/2)
        y += int((h-2*r)/2)

        cr.arc(r+x, r+y, r, 0, 360*PI_OVER_180)
        cr.close_path()
        return


class ShapeStar(Shape):

    def __init__(self, points, indent=0.61, direction=gtk.TEXT_DIR_LTR):
        self.coords = self._calc_coords(points, 1-indent)

    def _calc_coords(self, points, indent):
        coords = []
        step = radian(180.0/points)

        for i in range(2*points):
            if i%2:
                x = (sin(step*i)+1)*0.5
                y = (cos(step*i)+1)*0.5
            else:
                x = (sin(step*i)*indent+1)*0.5
                y = (cos(step*i)*indent+1)*0.5

            coords.append((x,y))
        return coords

    def layout(self, cr, x, y, w, h):
        points = map(lambda (sx,sy): (sx*w+x,sy*h+y), self.coords)
        cr.move_to(*points[0])

        for p in points[1:]:
            cr.line_to(*p)

        cr.close_path()
        return


class Style:

    def __init__(self):
        self.shape_map = self._load_shape_map()
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

    def __setitem__(self, item, value):
        if self.properties.has_key(item):
            self.properties[item] = value
            return
        logging.warn('Key does not exist in the style profile: %s' % item)
        return None

    def _load_shape_map(self):
        if gtk.widget_get_default_direction() != gtk.TEXT_DIR_RTL:
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

    def paint_bg_flat(self, cr, part, x, y, w, h, sxO=0, alpha=1.0):
        shape = self.shape_map[part.shape]
        state = part.state
        curv = self["curvature"]
        aw = self["arrow-width"]

        cr.save()

        cr.rectangle(x, y, w, h)
        cr.clip()
        cr.translate(x-sxO, y)

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=curv)
        lin = cairo.LinearGradient(0, 0, 0, h)
        r, g, b = color1.floats()
        lin.add_color_stop_rgba(0.0, r, g, b, alpha)
        r, g, b = color2.floats()
        lin.add_color_stop_rgba(1.0, r, g, b, alpha)

        cr.set_source(lin)
        cr.fill()

        cr.restore()
        return

    def paint_bg(self, cr, part, x, y, w, h, sxO=0, alpha=1.0):
        shape = self.shape_map[part.shape]
        state = part.state
        curv = self["curvature"]
        aw = self["arrow-width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)

        cr.clip()
        cr.translate(x-sxO, y)

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 1, 1, w, h-1, arrow_width=aw, radius=curv)
        lin = cairo.LinearGradient(0, 0, 0, h)
        r, g, b = color1.floats()
        lin.add_color_stop_rgba(0.0, r, g, b, alpha)
        r, g, b = color2.floats()
        lin.add_color_stop_rgba(1.0, r, g, b, alpha)

        cr.set_source(lin)
        cr.fill()

        cr.translate(0.5, 0.5)
        cr.set_line_width(1.0)

        # strong outline
        r, g, b = self.dark_line[state].floats()
        shape.layout(cr, 0, 0, w-1, h-1, arrow_width=aw, radius=curv)
        cr.set_source_rgba(r, g, b, alpha)
        cr.stroke_preserve()
        cr.set_source_rgba(r, g, b, 0.3*alpha)
        cr.stroke()

        # inner bevel/highlight
        shape.layout(cr, 1, 1, w-2, h-2, arrow_width=aw, radius=curv-1)
        if part.state != gtk.STATE_ACTIVE:
            r, g, b = self.light_line[state].floats()
            lin = cairo.LinearGradient(0, 0, 0, h)
            lin.add_color_stop_rgba(0.0, r, g, b, 0.7*alpha)
            lin.add_color_stop_rgba(1.0, r, g, b, 0.1)
            cr.set_source(lin)
            cr.stroke()
        else:
            r, g, b = self.dark_line[state].floats()
            alpha *= 0.23
            cr.set_source_rgba(r, g, b, alpha)
        cr.stroke()

        cr.restore()
        return

    def paint_bg_active_deep(self, cr, part, x, y, w, h, alpha=1.0):
        shape = self.shape_map[part.shape]
        state = part.state
        curv = self["curvature"]
        aw = self["arrow-width"]

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=curv)

        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(2.0, *color1.floats())
        lin.add_color_stop_rgb(0.0, *color2.floats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow 1
        shape.layout(cr, 2, 2, w-2, h-2, arrow_width=aw, radius=curv-2)
        r, g, b = self.dark_line[state].floats()
        cr.set_source_rgba(r, g, b, 0.1)
        cr.stroke()

        # inner shadow 2
        shape.layout(cr, 1, 1, w-1, h-1, arrow_width=aw, radius=curv-1)
        cr.set_source_rgba(r, g, b, 0.4)
        cr.stroke()

        # strong outline
        shape.layout(cr, 0, 0, w, h, arrow_width=aw, radius=curv)
        cr.set_source_rgb(*self.dark_line[state].floats())
        cr.stroke_preserve()
        cr.set_source_rgba(r, g, b, 0.5*alpha)
        cr.stroke()
        cr.restore()
        return

    def paint_layout(self, cr, widget, part, x, y, clip=None, sxO=0, etched=True):
        layout = part.layout

        a = 0.5
        if etched and CACHED_THEME_NAME == 'Ambiance-maverick-beta':
            if part.state == gtk.STATE_PRELIGHT:
                etched = False
            if part.is_active:
                if part.state == gtk.STATE_ACTIVE:
                    a = 0.3
                else:
                    a = 0.4

        if etched:
            pcr = pangocairo.CairoContext(cr)
            pcr.move_to(x, y+1)
            pcr.layout_path(layout)
            r,g,b = self.light_line[gtk.STATE_NORMAL].floats()
            pcr.set_source_rgba(r,g,b,a)
            pcr.fill()

        widget.style.paint_layout(widget.window,
                                  self.text_states[part.state],
                                  False,
                                  clip,   # clip area
                                  widget,
                                  'button',
                                  x, y,
                                  layout)
        return


class FramedSectionAlt(gtk.VBox):

    def __init__(self, xpadding=SPACING_MED):
        gtk.VBox.__init__(self)
        self.set_redraw_on_allocate(False)

        self.header_alignment = gtk.Alignment(xscale=1.0, yscale=1.0)
        self.header = gtk.HBox()
        self.header_vbox = gtk.VBox()
        header_vb_align = gtk.Alignment(0, 0.5)
        header_vb_align.add(self.header_vbox)
        self.header.pack_start(header_vb_align, False)

        self.header_alignment.add(self.header)
        self.header_alignment.set_padding(SPACING_SMALL,
                                          SPACING_SMALL,
                                          xpadding,
                                          xpadding)

        self.body_alignment = gtk.Alignment(xscale=1.0, yscale=1.0)
        self.body = gtk.VBox()
        self.body_alignment.add(self.body)
        self.body_alignment.set_padding(SPACING_MED, 0, 0, 0)

        self.body.set_spacing(SPACING_MED)

        self.pack_start(self.header_alignment, False)
        self.pack_start(self.body_alignment)

        self.image = gtk.Image()
        self.title = EtchedLabel()
        self.summary = gtk.Label()

        self.title.set_alignment(0,0.5)
        self.summary.set_alignment(0,0.5)

        self.summary.set_line_wrap(True)

        self.header_vbox.pack_start(self.title, False, False)
        self.header_vbox.pack_start(self.summary, False)
        # Make sure the user can select and copy the title/summary
        #self.label.set_selectable(True)
        return

    def set_icon_from_name(self, icon_name, icon_size=gtk.ICON_SIZE_MENU):
        self.image.set_from_icon_name(icon_name, icon_size)

        if not self.image.parent:
            self.header.pack_start(self.image, False)
            self.header.reorder_child(self.image, 0)
            self.image.show()
        return

    def set_icon_from_pixbuf(self, pixbuf):
        self.image.set_from_pixbuf(pixbuf)

        if not self.image.parent:
            self.header.pack_start(self.image, False)
            self.header.reorder_child(self.image, 0)
            self.image.show()
        return

    def set_title(self, label='', markup=None):
        if markup:
            self.title.set_markup(markup)
        else:
            self.title.set_markup('<small>%s</small>' % label)

        # atk stuff
        acc = self.get_accessible()
        acc.set_role(atk.ROLE_SECTION)
        return

    def set_summary(self, label='', markup=None):
        if markup:
            self.summary.set_markup(markup)
        else:
            self.summary.set_markup('<small>%s</small>' % label)

        # atk stuff
        acc = self.get_accessible()
        acc.set_role(atk.ROLE_SECTION)
        return

    def set_xpadding(self, xpadding):
        self.header_alignment.set_padding(0, 0, xpadding, xpadding)
        self.body_alignment.set_padding(0, 0, xpadding, xpadding)
        self.footer_alignment.set_padding(0, 0, xpadding, xpadding)
        return


class FramedSection(gtk.VBox):

    def __init__(self, label_markup=None, xpadding=SPACING_MED):
        gtk.VBox.__init__(self)
        self.set_redraw_on_allocate(False)

        self.header_alignment = gtk.Alignment(xscale=1.0, yscale=1.0)
        self.header = gtk.HBox()
        self.header_alignment.add(self.header)

        self.header_alignment.set_padding(SPACING_SMALL,
                                          SPACING_SMALL,
                                          xpadding,
                                          xpadding)

        self.body_alignment = gtk.Alignment(xscale=1.0, yscale=1.0)
        self.body = gtk.VBox()
        self.body_alignment.add(self.body)
        self.body_alignment.set_padding(SPACING_MED, 0, 0, 0)

        self.footer_alignment = gtk.Alignment(xscale=1.0, yscale=1.0)
        self.footer = gtk.HBox()
        self.footer_alignment.add(self.footer)
        self.footer_alignment.set_padding(0, 0,
                                          xpadding,
                                          xpadding)

        self.body.set_spacing(SPACING_MED)
        self.footer.set_size_request(-1, 2*EM)

        self.pack_start(self.header_alignment, False)
        self.pack_start(self.body_alignment)
        self.pack_start(self.footer_alignment, False)

        self.image = gtk.Image()
        self.label = EtchedLabel()
        # Make sure the user can select and copy the title/summary
        #self.label.set_selectable(True)
        self.header.pack_start(self.label, False)
        if label_markup:
            self.set_label(label_markup)
        return

    def set_icon_from_name(self, icon_name, icon_size=gtk.ICON_SIZE_MENU):
        self.image.set_from_icon_name(icon_name, icon_size)

        if not self.image.parent:
            self.header.pack_start(self.image, False)
            self.header.reorder_child(self.image, 0)
            self.image.show()
        return

    def set_icon_from_pixbuf(self, pixbuf):
        self.image.set_from_pixbuf(pixbuf)

        if not self.image.parent:
            self.header.pack_start(self.image, False)
            self.header.reorder_child(self.image, 0)
            self.image.show()
        return

    def set_label(self, label='', markup=None):
        if markup:
            self.label.set_markup(markup)
        else:
            self.label.set_markup('<b>%s</b>' % label)

        # atk stuff
        acc = self.get_accessible()
        acc.set_name(self.label.get_text())
        acc.set_role(atk.ROLE_SECTION)
        return

    def set_xpadding(self, xpadding):
        self.header_alignment.set_padding(0, 0, xpadding, xpadding)
        self.body_alignment.set_padding(0, 0, xpadding, xpadding)
        self.footer_alignment.set_padding(0, 0, xpadding, xpadding)
        return

    def draw(self, cr, a, expose_area, draw_border=True):
#        if not_overlapping(a, expose_area): return

#        cr.save()
#        cr.translate(0.5, 0.5)
#        cr.rectangle(a)
#        cr.clip_preserve()

        #a = self.header_alignment.allocation

        # fill section white
        #cr.rectangle(a)
        #cr.set_source_rgb(*floats_from_gdkcolor_wit(self.style.base[self.state]))
        #cr.fill()
        #cr.save()
#        cr.set_line_width(1)
#        cr.set_source_rgb(*floats_from_gdkcolor(self.style.dark[self.state]))
#        cr.stroke()
        #cr.restore()

#        cr.restore()
        return



class LayoutView2(gtk.HBox):

    def __init__(self, xspacing=4, yspacing=6):
        gtk.HBox.__init__(self, spacing=xspacing)
        self.set_homogeneous(True)

        self.min_col_width = 128
        self.n_columns = 0
        self.yspacing = yspacing

        self._allocation = None
        self._non_col_children = []

        self.connect('size-allocate', self._on_allocate, yspacing)
        #~ self.connect('expose-event', self._on_expose_debug)
        return

    def _on_allocate(self, widget, allocation, yspacing):
        if self._allocation == allocation: return True
        self._allocation = allocation
        w = allocation.width
        self.layout(w, yspacing, force=False)
        return True

    def _on_expose_debug(self, widget, event):
        cr = widget.window.cairo_create()

        for i, child in enumerate(self.get_children()):
            a = child.allocation
            cr.rectangle(a)

            if i%2:
                cr.set_dash((2,2))
                cr.set_source_rgb(1,0,0)
            else:
                cr.set_dash((2,2), 2)
                cr.set_source_rgb(0,1,0)

            cr.stroke()

        del cr
        return

    def add(self, child):
        self._non_col_children.append(child)
        return

    def clear(self):
        for w in self._non_col_children:
            w.destroy()

        self._non_col_children = []
        return

    def set_widgets(self, widgets):
        self.clear()
        for w in widgets:
            self._non_col_children.append(w)
        
        gobject.idle_add(self.layout, self.allocation.width, self.yspacing)
        return

    def layout(self, width, yspacing, force=True):
        n_cols = max(1, width / (self.min_col_width + self.get_spacing()))
        n_cols = min(len(self._non_col_children), n_cols)

        if self.n_columns == n_cols and not force:
            return True

        for i, col in enumerate(self.get_children()):
            for child in col.get_children():
                col.remove(child)

            if i >= n_cols:
                self.remove(col)
                col.destroy()

        if n_cols > self.n_columns:
            for i in range(self.n_columns, n_cols):
                col = gtk.VBox(spacing=yspacing)
                self.pack_start(col)

        cols = self.get_children()
        for i, child in enumerate(self._non_col_children):
            cols[i%n_cols].pack_start(child, False)

        self.show_all()
        self.n_columns = n_cols
        return


class LayoutView(FramedSection):

    def __init__(self):
        FramedSection.__init__(self)
        self.set_redraw_on_allocate(False)

        self.column_hbox = gtk.HBox(spacing=SPACING_SMALL)
        self.column_hbox.set_homogeneous(True)
        self.body.pack_start(self.column_hbox)

        self.n_columns = 0
        self.widget_list = []
        self.theme = get_mkit_theme()
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
#        width -= 100    # fudge number
        n_columns = width / widest_w
        n_columns = (width - n_columns*self.column_hbox.get_spacing()) / widest_w

        if n_columns > len(widgets):
            n_columns = len(widgets)
        if n_columns <= 0:
            n_columns = 1

        if n_columns == self.n_columns: return
        self.clear_columns()

        # pack columns into widget
        for i in range(n_columns):
            self.column_hbox.pack_start(gtk.VBox(spacing=SPACING_LARGE))

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
        self.n_columns = n_columns
        return

    def clear_all(self):
        # destroy all columns and column-children
        self.widget_list = []
        self.n_columns = 0
        for col in self.column_hbox.get_children():
            for child in col.get_children():
                child.destroy()
            col.destroy()
        return

    def clear_columns(self):
        # remove columns, but do not destroy column-children
        for col in self.column_hbox.get_children():
            for btn in col.get_children():
                col.remove(btn)
            col.destroy()
        return

    def draw(self, cr, a, expose_area):
        if not_overlapping(a, expose_area): return

#        cr.save()
#        FramedSection.draw(self, cr, a, expose_area)

        for btn in self.widget_list:
            a = btn.allocation
            if a.width == 1 or a.height == 1: break

            btn.draw(cr, a, expose_area)

#        cr.restore()
        return


class Button(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self._button_press_origin = None
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)

        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        self.connect('key-press-event', self._on_key_press)
        return

    def _on_button_press(self, btn, event):
        if event.button != 1:
            self.set_state(gtk.STATE_NORMAL)
            self.window.set_cursor(None)
            if hasattr(self, 'label_list'):
                for v in self.label_list:
                    l = getattr(self, v)
                    self._label_colorise_normal(l)
            return
        self._button_press_origin = btn
        self.set_state(gtk.STATE_ACTIVE)

        if hasattr(self, 'label_list'):
            for v in self.label_list:
                l = getattr(self, v)
                self._label_colorise_active(l)
        return

    def _on_button_release(self, btn, event):

        def clicked(w):
            w.emit('clicked')

        if event.button != 1:
            self.queue_draw()
            return

        region = gtk.gdk.region_rectangle(self.allocation)
        if not region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            self.set_state(gtk.STATE_NORMAL)
            return

        self._button_press_origin = None
        self.set_state(gtk.STATE_PRELIGHT)

        if hasattr(self, 'label_list'):
            for v in self.label_list:
                l = getattr(self, v)
                self._label_colorise_normal(l)

        gobject.timeout_add(50, clicked, btn)
        return

    def _on_enter(self, btn, event):
        if self == self._button_press_origin:
            self.set_state(gtk.STATE_ACTIVE)
        else:
            self.set_state(gtk.STATE_PRELIGHT)

        if not event.state:
            self.window.set_cursor(self._cursor)

        if event.state and event.state == gtk.gdk.BUTTON1_MASK:
            self.window.set_cursor(self._cursor)
            if hasattr(self, 'label_list'):
                for v in self.label_list:
                    l = getattr(self, v)
                    self._label_colorise_active(l)
        return

    def _on_leave(self, btn, event):
        self.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)

        if hasattr(self, 'label_list'):
            for v in self.label_list:
                l = getattr(self, v)
                self._label_colorise_normal(l)
        return

    def _on_key_press(self, btn, event):
        if (event.keyval != (gtk.gdk.keyval_from_name('Return') or
             gtk.gdk.keyval_from_name('KP_Enter'))):
            return

        def clicked(w):
            w.emit('clicked')

        gobject.timeout_add(50, clicked, btn)
        return

    def _label_colorise_active(self, label):
        c = self.style.base[gtk.STATE_SELECTED]

        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = label.get_layout()
        attrs = layout.get_attributes()

        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return

    def _label_colorise_normal(self, label):
        if self.state == gtk.STATE_PRELIGHT or \
            self.has_focus():
            if hasattr(label, 'is_subtle') and label.is_subtle:
                c = self.style.dark[self.state]
            else:
                c = self.style.text[self.state]
        else:
            c = self.style.text[self.state]

        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = label.get_layout()
        attrs = layout.get_attributes()

        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return


class LinkButtonLight(Button):

    def __init__(self):
        Button.__init__(self)
        self.label = EtchedLabel()
        self.add(self.label)
        self.show_all()

        self.label_list = ('label',)
        return

    def set_label(self, label):
        self.label.set_markup('<u>%s</u>' % label)
        return

    def draw(self, *args):
        return



class LinkButton(gtk.EventBox):

    """ A minimal LinkButton type widget """

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self, markup, icon_name, icon_size, icons=None):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_redraw_on_allocate(False)

        self.label = EtchedLabel()
        self.label.set_etching_alpha(0.55)
        self.image = gtk.Image()

        self._max_w = -1
        self._max_h = -1

        self._layout = None
        self._button_press_origin = None    # broken?
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)
        self._use_underline = False
        self._subdued = False
        self.alpha = 1.0

        if markup:
            self.set_label(markup)
        if icon_name:
            self.set_image_from_icon_name(icon_name, icon_size, icons)

        # atk stuff
        atk_obj = self.get_accessible()
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)
        # auto generated atk label
        atk_obj.set_name(self.label.get_text())

        self.shape = SHAPE_RECTANGLE
        self.theme = get_mkit_theme()

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
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        self.image.connect('expose-event', self._on_image_expose)
        return

    def _on_realize(self, widget):
        self.set_size_request(self.calc_width(), 
                              self.get_size_request()[1])
        if self._subdued:
            self._colorise_label_normal()
        return

    def _on_image_expose(self, widget, event):
        pb = self.image.get_pixbuf()
        a = widget.allocation
        x = a.x + (a.width - pb.get_width())/2
        y = a.y + (a.height - pb.get_height())/2
        cr = widget.window.cairo_create()

        cr.set_source_pixbuf(pb, x, y)
        cr.paint_with_alpha(self.alpha)

        if self.state not in (gtk.STATE_PRELIGHT, gtk.STATE_ACTIVE): return

        cr.rectangle(a)
        cr.clip_preserve()
        if self.state == gtk.STATE_PRELIGHT:
            r,g,b = floats_from_gdkcolor(self.style.mid[gtk.STATE_PRELIGHT])
        else:
            r,g,b = floats_from_gdkcolor(self.style.mid[gtk.STATE_SELECTED])
        cr.set_source_rgba(r,g,b, 0.125*self.alpha)
        cr.mask_surface(self._image_surface, x, y)
        return True

    def _on_enter(self, cat, event):
        if cat == self._button_press_origin:
            cat.set_state(gtk.STATE_ACTIVE)
        else:
            cat.set_state(gtk.STATE_PRELIGHT)
        self._colorise_label_normal()
        self.window.set_cursor(self._cursor)
        return

    def _on_leave(self, cat, event):
        cat.set_state(gtk.STATE_NORMAL)
        self._colorise_label_normal()
        self.window.set_cursor(None)
        return

    def _on_focus_in(self, *args):
        if self._subdued:
            self._colorise_label_normal()
        a = self.allocation
        self.queue_draw_area(a.x-3, a.y-3, a.width+6, a.height+6)
        return

    def _on_focus_out(self, *args):
        if self._subdued:
            self._colorise_label_normal()
        a = self.allocation
        self.queue_draw_area(a.x-3, a.y-3, a.width+6, a.height+6)
        return

    def _on_button_press(self, cat, event):
        if event.button != 1: return
        self._button_press_origin = cat
        cat.set_state(gtk.STATE_ACTIVE)
        self._colorise_label_active()
        return

    def _on_button_release(self, cat, event):
        def emit_clicked():
            self.emit('clicked')
            return False

        if event.button != 1:
            self.queue_draw()
            return

        cat_region = gtk.gdk.region_rectangle(cat.allocation)
        if not cat_region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            cat.set_state(gtk.STATE_NORMAL)
        else:
            self._button_press_origin = None
            cat.set_state(gtk.STATE_PRELIGHT)
        
        self._colorise_label_normal()
        gobject.timeout_add(50, emit_clicked)
        return

    def _on_key_press(self, cat, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self._colorise_label_active()
            cat.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, cat, event):
        def emit_clicked():
            self.emit('clicked')
            return False

        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            self._colorise_label_normal()
            cat.set_state(gtk.STATE_NORMAL)
            gobject.timeout_add(100, emit_clicked)
        return

    def _colorise_label_active(self):
        c = gtk.gdk.color_parse(LINK_ACTIVE_COLOR)
        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = self.label.get_layout()
        attrs = layout.get_attributes()
        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return

    def _colorise_label_normal(self):
        if not self._subdued or self.state == gtk.STATE_PRELIGHT or \
            self.has_focus():
            c = self.style.text[self.state]
        else:
            c = self.style.dark[self.state]

        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = self.label.get_layout()
        attrs = layout.get_attributes()
        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return

    def _cache_image_surface(self, pb):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                  pb.get_width(),
                                  pb.get_height())
        cr = cairo.Context(surf)
        cr = gtk.gdk.CairoContext(pangocairo.CairoContext(cr))
        cr.set_source_pixbuf(pb, 0,0)
        cr.paint()
        self._image_surface = surf
        del cr
        return

    def set_underline(self, use_underline):
        self._use_underline = use_underline

        if use_underline:
            l = self.label.get_label()
            self.label.set_label('<u>%s</u>' % l)
        else:
            m = self.label.get_markup()
            m.replace('<u>', '').replace('</u>', '')
            self.label.set_markup(m)
        return

    def set_subdued(self, is_subdued):
        self._subdued = is_subdued
        if self.window:
            self._colorise_label_normal()
        return

    def set_xmargin(self, xmargin):
        return

    def set_internal_xalignment(self, xalign):
        #~ self.alignment.set(xalign,
                           #~ self.alignment.get_property('yalign'),
                           #~ 0, 0)    # x/y scale
        return

    def set_internal_spacing(self, internal_spacing):
        self.box.set_spacing(internal_spacing)
        return

    def set_label(self, label):
        if self._use_underline:
            self.label.set_markup('<u>%s</u>' % label)
        else:
            self.label.set_markup(label)
        w = self.calc_width()
        self.set_size_request(w, self.get_size_request()[1])
        return
        
    def get_label(self):
        return self._markup

    def set_image_from_icon_name(self, icon_name, icon_size, icons=None):
        icons = icons or gtk.icon_theme_get_default()
        try:
            pb = icons.load_icon(icon_name, icon_size, 0)
        except:
            return
        self.image.set_from_pixbuf(pb)
        self._cache_image_surface(pb)
        return

    def set_image_from_pixbuf(self, pb):
        self.image.set_from_pixbuf(pb)
        self._cache_image_surface(pb)
        return

    def draw(self, cr, a, expose_area, alpha=1.0, focus_draw=True):
        if not_overlapping(a, expose_area): return

        if self.has_focus() and focus_draw:
            a = self.label.allocation
            x, y, w, h = a.x, a.y, a.width, a.height
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x-3, y-1, w+6, h+2),
                                   self,
                                   'expander',
                                   x-3, y-1, w+6, h+2)
        return


class EtchedLabel(gtk.Label):
    
    def __init__(self, *args, **kwargs):
        gtk.Label.__init__(self, *args, **kwargs)
        self.alpha = 0.5
        self.connect('expose-event', self._on_expose)
        return

    def set_etching_alpha(self, a):
        self.alpha = a
        return

    def _on_expose(self, widget, event):
        l = self.get_layout()
        a = widget.allocation

        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        pc = pangocairo.CairoContext(cr)

        xp, yp = self.get_padding()

        x, y = a.x+xp, a.y+1+yp
        w, h = a.width, a.height

        lw, lh = l.get_pixel_extents()[1][2:]
        ax, ay = self.get_alignment()

        if lw < w:
            x += int((w-2*xp-lw)*ax)
        if lh < h:
            y += int((h-2*yp-lh)*ay)

        pc.move_to(x, y)
        pc.layout_path(l)
        r,g,b = floats_from_gdkcolor(self.style.light[self.state])
        pc.set_source_rgba(r,g,b,self.alpha)
        pc.fill()
        del pc
        return

    def set_max_line_count(self, *args):
        return


class HLinkButton(LinkButton):

    def __init__(self, markup=None, icon_name=None, icon_size=20, icons=None):
        LinkButton.__init__(self, markup, icon_name, icon_size)

        self.box = gtk.HBox()
        self.add(self.box)

        if not self.image.get_storage_type() == gtk.IMAGE_EMPTY:
            self.box.pack_start(self.image, False)
        if self.label.get_text():
            a = gtk.Alignment(1.0, 0.5, yscale=1.0)
            a.add(self.label)
            self.box.pack_start(a, False)

        self.show_all()
        return

    def calc_width(self):
        w = 1
        spacing = 0

        if self.label:
            pc = self.get_pango_context()
            layout = pango.Layout(pc)
            layout.set_markup(self.label.get_label())
            w += layout.get_pixel_extents()[1][2]

        if self.image and self.image.get_property('visible'):
            w += self.image.allocation.width
            spacing = self.box.get_spacing()

        w += 2*self.get_border_width() + spacing
        return w


class VLinkButton(LinkButton):

    def __init__(self, markup=None, icon_name=None, icon_size=20, icons=None):
        LinkButton.__init__(self, markup, icon_name, icon_size)

        self.box = gtk.VBox(spacing=SPACING_SMALL)
        self.add(self.box)

        if not self.image.get_storage_type() == gtk.IMAGE_EMPTY:
            self.box.pack_start(self.image, False)
        if self.label.get_text():
            self.box.pack_start(self.label)
            self.label.set_max_line_count(2)
            self.label.set_alignment(0.5, 0)
            self.label.set_justify(gtk.JUSTIFY_CENTER)
            self.box.reorder_child(self.label, -1)

        self.set_border_width(BORDER_WIDTH_SMALL)
        self.show_all()
        #self.connect('expose-event', self._DEBUG_on_expose)
        return

    def set_max_width(self, w):
        self._max_w = w

    def calc_width(self):
        w = 1
        iw = 0

        if self.label:
            pc = self.get_pango_context()
            layout = pango.Layout(pc)
            layout.set_markup(self.label.get_label())
            lw = layout.get_pixel_extents()[1][2]   # label width

        if self.image and self.image.get_property('visible'):
            iw = self.image.allocation.width        # image width

        w = max(lw, iw) + 2*self.get_border_width()

        if self._max_w > 0 and w >= self._max_w:
            w = self._max_w
        return w

    def _DEBUG_on_expose(self, widget, event):
        # handy for debugging layouts
        # draw bounding boxes
        cr = widget.window.cairo_create()
        cr.set_source_rgba(0, 0, 1, 0.5)
        cr.rectangle(widget.allocation)
        cr.stroke()

        cr.translate(0.5,0.5)
        cr.set_line_width(1)

        cr.set_source_rgb(1, 0, 1)
        cr.rectangle(self.image.allocation)
        cr.stroke()

        cr.set_source_rgb(1, 0, 0)
        cr.rectangle(self.label.allocation)
        cr.stroke()
        return
        cr.set_source_rgb(0, 1, 0)
        x,y,w,h = self.label.get_layout().get_pixel_extents()[1]
        x += self.label.allocation.x
        y += self.label.allocation.y
        cr.rectangle(x,y,w,h)
        cr.stroke()
        del cr


class BubbleLabel(gtk.Label):

    def __init__(self):
        gtk.Label.__init__(self)
        self.set_alignment(0,0)
        self.set_padding(4, 0)
        self.shape = ShapeRoundedRectangle()
        return

    def set_text(self, markup):
        gtk.Label.set_markup(self, '<span color="white">%s</span>' % markup)
        return

    def set_markup(self, markup):
        gtk.Label.set_markup(self, '<span color="white">%s</span>' % markup)
        return

    def draw(self, cr, a, event_area):
        if not self.get_property('visible'): return

        cr.save()
        xp = self.get_padding()[0]
        ax, ay = self.get_alignment()
        lx, ly, lw, lh = self.get_layout().get_pixel_extents()[1]
        x = int(a.x + (a.width-lw)*ax)
        y = int(a.y + (a.height-lh)*ay)
        self.shape.layout(cr, x, y, x+lw+2*xp, y+lh, radius=3)
        cr.set_source_rgba(0, 0, 0, 0.55)
        cr.fill()
        cr.restore()
        return


class MoreLabel(gtk.EventBox):

    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.label = l = EtchedLabel()
        l.set_alignment(0,0.5)
        l.set_padding(6, 4)

        self.add(l)

        self.theme = get_mkit_theme()
        self.shape = SHAPE_RECTANGLE

        self.ishover = False
        return

    def set_text(self, markup):
        gtk.Label.set_markup(self.label, '<small>%s</small>' % markup)
        return

    def set_markup(self, markup):
        gtk.Label.set_markup(self.label, '<small>%s</small>' % markup)
        return

    def draw(self, cr, a, event_area):
        if not self.get_property('visible'): return True

        if self.state == gtk.STATE_PRELIGHT:
            self.set_state(gtk.STATE_NORMAL)
        self.theme.paint_bg(cr, self, a.x, a.y+2, a.width, a.height-4)
        return

