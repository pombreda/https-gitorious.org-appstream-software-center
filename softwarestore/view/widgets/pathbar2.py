# Copyright (C) 2009 Matthew McGowan
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
import glib
import cairo
import pango
import gobject


# my constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

# shape constants
SHAPE_RECTANGLE = 0
SHAPE_START_ARROW = 1
SHAPE_MID_ARROW = 2
SHAPE_END_CAP = 3


class PathBar(gtk.DrawingArea):

    def __init__(self, min_part_width=56, xpadding=10, ypadding=8,
        spacing=6, curvature=4, arrow_width=13):

        gtk.DrawingArea.__init__(self)
        self.set_redraw_on_allocate(False)

        self.__shapes = {
            SHAPE_RECTANGLE : self.__shape_rect,
            SHAPE_START_ARROW : self.__shape_start_arrow,
            SHAPE_MID_ARROW : self.__shape_mid_arrow,
            SHAPE_END_CAP : self.__shape_end_cap}

        self.__parts = []

        self.__active_part = None
        self.__focal_part = None

        self.__scroller = None
        self.__scroll_xO = 0

        self.min_part_width = min_part_width
        self.xpadding = xpadding
        self.ypadding = ypadding
        self.spacing = spacing
        self.curvature = curvature
        self.arrow_width = arrow_width

        # setup event handling
        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.POINTER_MOTION_MASK|
                        gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.connect("motion-notify-event", self.__motion_notify_cb)
        self.connect("leave-notify-event", self.__leave_notify_cb)
        self.connect("button-press-event", self.__button_press_cb)
        self.connect("button-release-event", self.__button_release_cb)
        self.connect("key-release-event", self.__key_release_cb)

        self.connect("expose-event", self.__expose_cb)
        self.connect("style-set", self.__style_change_cb)
        self.connect("size-allocate", self.__allocation_change_cb)
        return

    def set_active_part(self, part):
        prev_active = self.__active_part

        if prev_active and prev_active != part:
            prev_active.set_state(gtk.STATE_NORMAL)

        part.set_state(gtk.STATE_ACTIVE)
        self.__active_part = part
        return

    def get_active_part(self):
        return self.__active_part

    def get_path_width(self):
        if len(self.__parts) == 0:
            return 0
        a = self.__parts[-1].get_allocation()
        return a.x + a.width

    def append(self, part):
        # the basics
        self.__srcoll_xO = 0
        x = self.get_path_width()
        self.__parts.append(part)
        part.set_pathbar(self)
        self.set_active_part(part)

        # determin part shapes, and calc modified parts widths
        prev = self.__compose_parts(part)

        # set the position of new part
        part.set_x(x)

        # check parts fit to widgets allocated width
        did_shrink = self.__shrink_check(self.allocation)

        if self.get_property("visible"):
            aw = self.arrow_width

            if did_shrink:
                # draw everything up to the tail of the prev part less arrow_width
                a = prev.get_allocation()
                self.queue_draw_area(0, 0, a.x + a.width - aw,
                    self.allocation.height)

                # calc the draw area for the scroll
                # we want clip as much as possible, so we only want to draw the
                # tail of the prev part + the area to be occupied of the scrolling
                # part. ok?
                draw_area = gtk.gdk.Rectangle(
                    part.get_x() - aw,
                    0,
                    part.get_width() + aw,
                    self.allocation.height)

                # begin scroll animation
                self.__hscroll(
                    part.get_width(),
                    draw_area
                    )

            elif prev:
                # see above comments for further explaination...
                # draw all of the prev part less arrow_width
                a = prev.get_allocation()
                self.queue_draw_area(a.x, 0,
                    a.width - aw,
                    self.allocation.height)

                draw_area = gtk.gdk.Rectangle(
                    part.get_x() - aw,
                    0,
                    part.get_width() + aw,
                    self.allocation.height)

                self.__hscroll(
                    part.get_width(),
                    draw_area
                    )

            else:
               self.queue_draw_area(0, 0, part.get_allocation().width,
                    self.allocation.height)
        return

    def shorten(self, n=1):
        n = int(n)
        if len(self.__parts)-n < 1:
            print 'The first part is sacred'
            return

        old_w = self.get_path_width()
        del self.__parts[-n:]

        self.__compose_parts(self.__parts[-1])
        self.__grow_check(old_w, self.allocation)

        if self.get_property("visible"):
            self.queue_draw()
        return

    def __shrink_check(self, allocation):
        path_w = self.get_path_width()
        if path_w <= allocation.width or allocation.width == 1:
            return False

        shrinkage = path_w - allocation.width
        mpw = self.min_part_width
        xO = 0

        for part in self.__parts[:-1]:
            w = part.get_width()
            dw = 0

            if w - shrinkage <= mpw:
                dw = w - mpw
                shrinkage -= dw
                part.set_size(mpw, -1)
                part.set_x(part.get_x() - xO)

            else:
                part.set_size(w - shrinkage, -1)
                part.set_x(part.get_x() - xO)
                dw = shrinkage
                shrinkage = 0

            xO += dw

        last = self.__parts[-1]
        last.set_x(last.get_x() - xO)
        return True

    def __grow_check(self, old_width, allocation):
        if old_width < allocation.width:
            return False

        parts = self.__parts
        growth = old_width - self.get_path_width()
        parts.reverse()

        for part in parts:
            bw = part.get_best_fit()[0]
            w = part.get_width()

            if part.is_truncated():
                dw = bw - w

                if dw <= growth:
                    growth -= dw
                    part.set_size(bw, -1)
                    part.set_x(part.get_x() + growth)

                else:
                    part.set_size(w + growth, -1)
                    growth = 0

            else:
                part.set_x(part.get_x() + growth)

        parts.reverse()
        shift =  parts[0].get_x()

        if shift > 0:
            for part in parts: part.set_x(part.get_x() - shift)
        return

    def __compose_parts(self, last):
        parts = self.__parts

        if len(parts) == 1:
            last.set_shape(SHAPE_RECTANGLE)
            last.set_size(*last.calc_best_fit())
            prev = None

        elif len(parts) == 2:
            prev = parts[0]
            prev.set_shape(SHAPE_START_ARROW)
            prev.set_size(*prev.calc_best_fit())

            last.set_shape(SHAPE_END_CAP)
            last.set_size(*last.calc_best_fit())

        else:
            prev = parts[-2]
            prev.set_shape(SHAPE_MID_ARROW)
            prev.set_size(*prev.calc_best_fit())

            last.set_shape(SHAPE_END_CAP)
            last.set_size(*last.calc_best_fit())

        return prev

    def __hscroll(self, distance, draw_area, duration=150, fps=50):
        # clean up any exisitng scroll callbacks
        if self.__scroller: gobject.source_remove(self.__scroller)

        sec = duration*0.001
        interval = int(duration/(sec*fps))  # duration / n_frames

        self.__scroller = gobject.timeout_add(
            interval,
            self.__hscroll_cb,
            sec,
            1/sec,
            distance,
            gobject.get_current_time() + sec,
            draw_area.x,
            draw_area.y,
            draw_area.width,
            draw_area.height)
        return

    def __hscroll_cb(self, sec, sec_inv, distance, end_t, x, y, w, h):
        cur_t = gobject.get_current_time()
        xO = distance*(sec - (end_t - cur_t))*sec_inv

        if xO < distance:
            self.__scroll_xO = xO
            self.queue_draw_area(x, y, w, h)
        else:   # final frame
            self.__scroll_xO = 0
            self.queue_draw()
            return False

        return True

    def __draw_hscroll(self, cr):
        # draw the last two parts
        prev, last = self.__parts[-2:]

        self.__draw_part(cr, last, self.style, self.curvature, 
            self.arrow_width, True)

        self.__draw_part(cr, prev, self.style, self.curvature, 
            self.arrow_width, False)
        return

    def __draw_all(self, cr):
        style = self.style
        r = self.curvature
        aw = self.arrow_width

        # draw parts in reverse order
        self.__parts.reverse()

        for part in self.__parts:
            self.__draw_part(cr, part, style, r, aw)

        self.__parts.reverse()
        return

    def __draw_part(self, cr, part, style, r, aw, is_scrolling=False):
        alloc = part.get_allocation()
        shape = part.shape
        state = part.state
        icon_pb = part.icon.pixbuf

        cr.save()
        sxO = 0
        if is_scrolling: sxO = part.get_width() - self.__scroll_xO
        cr.translate(alloc.x-sxO, alloc.y)

        # draw bg
        self.__draw_part_bg(
            cr,
            alloc.width,
            alloc.height,
            state,
            shape,
            style,
            r,
            aw)

        # determine left margin.  left margin depends on part shape
        # and whether there exists an icon or not
        if shape == SHAPE_MID_ARROW or shape == SHAPE_END_CAP:
            margin = int(1.5*self.arrow_width)
        else:
            margin = self.xpadding

        # draw icon
        if icon_pb:
            cr.set_source_pixbuf(
                icon_pb,
                self.xpadding-sxO,
                (alloc.height - icon_pb.get_height())/2)
            cr.paint()
            margin += icon_pb.get_width() + self.spacing

        # if space is limited and an icon is set, dont draw label
        if alloc.width == self.min_part_width and icon_pb:
            pass

        # otherwise, draw label
        else:
            dst_x = alloc.x + margin
            dst_y = self.ypadding + 1   # +1 for artistic license :)
            style.paint_layout(
                self.window,
                state,
                True,
                (dst_x-int(sxO), dst_y) + part.get_layout().get_pixel_size(),   # clip area
                self,
                None,
                dst_x-int(sxO),
                dst_y,
                part.get_layout())

        cr.restore()
        return

    def __draw_part_bg(self, cr, w, h, state, shape, style, r, aw):
        # determine colour scheme based on part state
        light = style.light[state]
        mid = style.mid[state]
        dark = style.dark[state]

        # make an active part look pressed in
        if state != gtk.STATE_ACTIVE:
            bg_alpha = 0.22
            bevel = light
        else:
            bg_alpha = 0.15
            bevel = mid

        # bg linear vertical gradient
        self.__shapes[shape](cr, 1, 1, w-1, h-1, r, aw)

        lin = cairo.LinearGradient(0, 0, 0, h-1)
        lin.add_color_stop_rgb(0, *rgb.lighten(mid, bg_alpha))
        lin.add_color_stop_rgb(1, mid.red_float, mid.green_float, mid.blue_float)
        cr.set_source(lin)
        cr.fill()

        # translate x,y by 0.5 so 1px lines are crisp
        cr.save()
        cr.translate(0.5, 0.5)
        cr.set_line_width(1.0)

        # outter slight bevel
        self.__shapes[shape](cr, 0, 0, w-1, h-1, r, aw)
        cr.set_source_rgba(0, 0, 0, 0.06)
        cr.stroke()

        # strong outline
        self.__shapes[shape](cr, 1, 1, w-2, h-2, r-0.5, aw)

        cr.set_source_rgb(
            dark.red_float,
            dark.green_float,
            dark.blue_float
            )
        cr.stroke()

        # inner bevel/highlight
        self.__shapes[shape](cr, 2, 2, w-3, h-3, r-1, aw)
        cr.set_source_rgba(
            bevel.red_float,
            bevel.green_float,
            bevel.blue_float,
            0.6)
        cr.stroke()

        cr.restore()
        return

    def __shape_rect(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def __shape_start_arrow(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w, (h+y)*0.5)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def __shape_mid_arrow(self, cr, x, y, w, h, r, aw):
        cr.move_to(-1, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w, (h+y)*0.5)
        cr.line_to(w-aw, h)
        cr.line_to(-1, h)
        cr.close_path()
        return

    def __shape_end_cap(self, cr, x, y, w, h, r, aw):
        global M_PI, PI_OVER_180
        cr.move_to(0, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(0, h)
        cr.close_path()
        return

    def __motion_notify_cb(self, widget, event):
        return

    def __leave_notify_cb(self, widget, event):
        return

    def __button_press_cb(self, widget, event):
        return

    def __button_release_cb(self, widget, event):
        return

    def __key_release_cb(self, widget, event):
        return

    def __expose_cb(self, widget, event):
        #t = gobject.get_current_time()
        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        if self.__scroll_xO > 0:
            self.__draw_hscroll(cr)
        else:
            self.__draw_all(cr)

        #print 'Exposure fps: %s' % (1 / (gobject.get_current_time() - t))
        return

    def __style_change_cb(self, widget, old_style):
        return

    def __allocation_change_cb(self, widget, allocation):
        return


class PathPart:

    def __init__(self, label=None, callback=None, args=()):

        self.__cb = callback
        self.__cbargs = args

        self.__best_fit = (0,0)
        self.__layout = None
        self.__pbar = None

        self.allocation = [0, 0, 0, 0]
        self.state = gtk.STATE_NORMAL
        self.shape = SHAPE_RECTANGLE

        self.label = label or ''
        self.icon = Icon()
        return

    def set_label(self, label):
        self.label = label
        return

    def set_icon_from_stock(self, stock_icon, size):
        style = gtk.Style()
        icon_set = style.lookup_icon_set(stock_icon)
        pb = icon_set.render_icon(
            style,
            gtk.TEXT_DIR_NONE,
            self.state,
            size,
            self.__pbar,
            None)

        self.icon = Icon(stock_icon, size, pb)
        return

    def set_state(self, gtk_state):
        self.state = gtk_state
        return

    def set_shape(self, shape):
        self.shape = shape
        return

    def set_x(self, x):
        if x != -1: self.allocation[0] = int(x)
        return

    def set_size(self, w, h):
        if w != -1: self.allocation[2] = int(w)
        if h != -1: self.allocation[3] = int(h)
        self.__calc_layout_width(self.__layout, self.shape, self.__pbar)
        return

    def set_pathbar(self, path_bar):
        self.__pbar = path_bar
        return

    def set_callback(self, callback, *args):
        self.__cb = callback
        self.__cbargs = args
        return

    def get_x(self):
        return self.allocation[0]

    def get_width(self):
        return self.allocation[2]

    def get_height(self):
        return self.allocation[3]

    def get_allocation(self):
        return gtk.gdk.Rectangle(*self.allocation)

    def get_best_fit(self):
        return self.__best_fit

    def get_layout(self):
        return self.__layout

    def get_has_callback(self):
        return self.__cb != None

    def do_callback(self):
        if self.__cb:
            self.__cb(*self.__cbargs)
        else:
            print 'Error: No callback has been set.'
        return

    def is_truncated(self):
        return self.__best_fit[0] != self.allocation[2]

    def calc_best_fit(self):
        pbar = self.__pbar

        # determine widget size base on label width
        self.__layout, size = self.__layout_text(
            self.label,
            pbar.get_pango_context())

        # calc text width + 2 * padding, text height + 2 * ypadding
        w = size[0] + 2*pbar.xpadding
        h = max(size[1] + 2*pbar.ypadding, pbar.get_size_request()[1])

        # if height greater than current height request,
        # reset height request to higher value
        # i get the feeling this should be in set_size_request(), but meh
        if h > pbar.get_size_request()[1]:
            pbar.set_size_request(-1, h)

        # if has icon add some more pixels on
        if self.icon.pixbuf:
            w += self.icon.pixbuf.get_width() + pbar.spacing

        # extend width depending on part shape  ...
        if self.shape == SHAPE_START_ARROW or self.shape == SHAPE_END_CAP:
            w += pbar.arrow_width

        elif self.shape == SHAPE_MID_ARROW:
            w += 2*pbar.arrow_width

        self.__best_fit = (w,h)
        return w, h

    def __layout_text(self, text, pango_context):
        # escape special characters
        text = glib.markup_escape_text(text.strip())
        layout = pango.Layout(pango_context)
        layout.set_markup('<b>%s</b>' % text)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        return layout, layout.get_pixel_size()

    def __calc_layout_width(self, layout, shape, pbar):
        # set layout width
        if self.icon.pixbuf:
            icon_w = self.icon.pixbuf.get_width() + pbar.spacing
        else:
            icon_w = 0

        w = self.allocation[2]
        if shape == SHAPE_MID_ARROW or shape == SHAPE_END_CAP:
            layout.set_width((w - pbar.arrow_width -
                2*pbar.xpadding - icon_w)*pango.SCALE)

        elif shape == SHAPE_START_ARROW:
            layout.set_width(int((w - 2.5*pbar.xpadding -
                icon_w)*pango.SCALE))
        else:
            layout.set_width((w - 2*pbar.xpadding - icon_w)*pango.SCALE)
        return


class Icon:

    def __init__(self, name=None, size=None, pixbuf=None):
        self.name = name
        self.size = size
        self.pixbuf = pixbuf
        return

    def set_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        return
