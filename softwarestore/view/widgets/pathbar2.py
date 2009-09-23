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
import cairo
import pango
import gobject


# print colours
WARNING = "\033[93m"
FAIL = "\033[91m"
ENDC = "\033[0m"

# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

# shape constants
SHAPE_RECTANGLE = 0
SHAPE_START_ARROW = 1
SHAPE_MID_ARROW = 2
SHAPE_END_CAP = 3


class PathBar(gtk.DrawingArea, gobject.GObject):

    def __init__(self, group=None, min_part_width=56, xpadding=10, ypadding=4,
        spacing=6, curvature=4, arrow_width=13):
        gobject.GObject.__init__(self)
        gtk.DrawingArea.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_size_request(-1, 30)

        self.__shapes = {
            SHAPE_RECTANGLE : self.__shape_rect,
            SHAPE_START_ARROW : self.__shape_start_arrow,
            SHAPE_MID_ARROW : self.__shape_mid_arrow,
            SHAPE_END_CAP : self.__shape_end_cap}

        self.__parts = []
        self.id_to_part = {}
        self.id_to_callback = {}

        self.__active_part = None
        self.__focal_part = None

        self.__scroller = None
        self.__scroll_xO = 0

        # global gtk settings we are interested in
        settings = gtk.settings_get_default()
        self.animate = settings.get_property("gtk-enable-animations")

        # custom widget specific settings
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
        return prev_active

    def get_active_part(self):
        return self.__active_part

    def get_left_part(self):
        active = self.get_active_part()
        if not active:
            return self.__parts[0]

        i = self.__parts.index(active)+1
        if i > len(self.__parts)-1:
            i = 0
        return self.__parts[i]

    def get_right_part(self):
        active = self.get_active_part()
        if not active:
            return self.__parts[0]

        i = self.__parts.index(active)-1
        if i < 0:
            i = len(self.__parts)-1
        return self.__parts[i]

    def add_with_id(self, label, callback, id):
        """
        Add a new button with the given label/callback
        
        If there is the same id already, replace the existing one
        with the new one
        """
        # check if we have the button of that id or need a new one
        if id in self.id_to_part:
            part = self.id_to_part[id]
            part.set_label(label)
            part.disconnect(self.id_to_callback[id])
            self.queue_draw_area(*part.allocation)
        else:
            part = PathPart(label)
            part.set_pathbar(self)
            self.append(part)
            self.id_to_part[id] = part

        # common code
        handler_id = part.connect("clicked", callback)
        self.id_to_callback[id] = handler_id
        return

    def remove_id(self, id):

        if not id in self.id_to_part:
            print 'id not in pathbar'
            return

        try:
            del self.id_to_callback[id]
        except KeyError:
            pass

        old_w = self.__draw_width()
        end_active = self.get_active_part() == self.__parts[-1]

        if len(self.__parts)-1 < 1:
            print WARNING + 'The first part is sacred ;)' + ENDC
            return

        del self.__parts[self.__parts.index(self.id_to_part[id])]
        del self.id_to_part[id]
        self.__compose_parts(self.__parts[-1], False)

        if end_active:
            self.set_active_part(self.__parts[-1])

        if old_w >= self.allocation.width:
            self.__grow_check(old_w, self.allocation)
            self.queue_draw()

        else:
            a = self.__parts[-1].get_allocation()
            new_w = self.__draw_width()
            self.queue_draw_area(a.x, 0, a.width+old_w-new_w, self.allocation.height)
        return

    def remove_all(self):
        """remove all elements"""
        for id, part in self.id_to_part.iteritems():
            self.remove_part_by_id(id)

        self.__parts = []
        self.id_to_part = {}
        self.id_to_callback = {}
        self.queue_draw()
        return

    def get_part_from_id(self, id):
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
        return self.id_to_part[id].get_label()

    def append(self, part):

        prev, did_shrink = self.__append(part)

        if not self.get_property("visible"):
            return

        if self.animate:
            aw = self.arrow_width

            if did_shrink:
                # because much has likely changed...
                # draw everything up to the tail of the prev part less arrow_width
                a = prev.get_allocation()
                self.queue_draw_area(0, 0, a.x + a.width - aw,
                    self.allocation.height)

            if prev:
                a = prev.get_allocation()
                self.queue_draw_area(a.x, 0, a.width-aw,
                    self.allocation.height)

            # calc the draw area for the scroll
            # we want clip as much as possible, so we only want to draw the
            # tail of the prev part + the area to be occupied by the scrolling
            # part. ok?
            draw_area = gtk.gdk.Rectangle(
                part.get_x()-1,
                0,
                part.get_width()+1,
                self.allocation.height)

            # begin scroll animation
            self.__hscroll_init(
                part.get_width(),
                draw_area
                )
        else:
            self.queue_draw()
        return

    def shorten(self, n=1):

        old_w, did_grow = self.__shorten(n)

        if not self.get_property("visible"):
            return

        if did_grow:
            self.queue_draw()

        else:
            a = self.__parts[-1].get_allocation()
            new_w = self.__draw_width()
            self.queue_draw_area(a.x, 0, a.width+old_w-new_w, self.allocation.height)
        return

    def __append(self, part):
        # clean up any exisitng scroll callbacks
        if self.__scroller:
            gobject.source_remove(self.__scroller)
        self.__scroll_xO = 0

        # the basics
        x = self.__draw_width()
        self.__parts.append(part)
        part.set_pathbar(self)

        prev_active = self.set_active_part(part)
        if prev_active and prev_active != part:
            self.queue_draw_area(*prev_active.allocation)

        # determin part shapes, and calc modified parts widths
        prev = self.__compose_parts(part, True)

        # set the position of new part
        part.set_x(x)

        # check parts fit to widgets allocated width
        if x + part.get_width() > self.allocation.width and \
            self.allocation.width != 1:
            self.__shrink_check(self.allocation)
            return prev, True

        return prev, False

    def __shorten(self, n):
        n = int(n)
        old_w = self.__draw_width()
        end_active = self.get_active_part() == self.__parts[-1]

        if len(self.__parts)-n < 1:
            print WARNING + 'The first part is sacred ;)' + ENDC
            return old_w, False

        del self.__parts[-n:]
        self.__compose_parts(self.__parts[-1], False)

        if end_active:
            self.set_active_part(self.__parts[-1])

        if old_w >= self.allocation.width:
            self.__grow_check(old_w, self.allocation)
            return old_w, True

        return old_w, False

    def __shrink_check(self, allocation):
        path_w = self.__draw_width()
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
        return

    def __grow_check(self, old_width, allocation):
        parts = self.__parts
        if len(parts) == 0:
            return

        growth = old_width - self.__draw_width()
        parts.reverse()

        for part in parts:
            bw = part.get_best_fit()[0]
            w = part.get_width()

            if w < bw:
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

        # left align parts
        if shift > 0:
            for part in parts: part.set_x(part.get_x() - shift)
        return

    def __compose_parts(self, last, prev_set_size):
        parts = self.__parts

        if len(parts) == 1:
            last.set_shape(SHAPE_RECTANGLE)
            last.set_size(*last.calc_best_fit())
            prev = None

        elif len(parts) == 2:
            prev = parts[0]
            prev.set_shape(SHAPE_START_ARROW)
            prev.calc_best_fit()

            last.set_shape(SHAPE_END_CAP)
            last.set_size(*last.calc_best_fit())

        else:
            prev = parts[-2]
            prev.set_shape(SHAPE_MID_ARROW)
            prev.calc_best_fit()

            last.set_shape(SHAPE_END_CAP)
            last.set_size(*last.calc_best_fit())

        if prev and prev_set_size:
            prev.set_size(*prev.get_best_fit())
        return prev

    def __draw_width(self):
        if len(self.__parts) == 0:
            return 0
        a = self.__parts[-1].get_allocation()
        return a.x + a.width

    def __hscroll_init(self, distance, draw_area, duration=150, fps=60):
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
            self.queue_draw_area(x, y, w, h)
            self.__scroller = None
            return False

        return True

    def __part_at_xy(self, x, y):

        for part in self.__parts:
            a = part.get_allocation()
            region = gtk.gdk.region_rectangle(a)

            if region.point_in(int(x), int(y)):
                return part

        return None

    def __draw_hscroll(self, cr):
        # draw the last two parts
        prev, last = self.__parts[-2:]

        self.__draw_part(cr, last, self.style, self.curvature,
            self.arrow_width, self.__shapes,
            last.get_width() - self.__scroll_xO)

        self.__draw_part(cr, prev, self.style, self.curvature,
            self.arrow_width, self.__shapes)
        return

    def __draw_all(self, cr, event_area):
        style = self.style
        r = self.curvature
        aw = self.arrow_width
        shapes = self.__shapes
        region = gtk.gdk.region_rectangle(event_area)

        # if a scroll is pending we want to not draw the final part,
        # as we don't want to prematurely reveal the part befor the
        # scroll animation has had a chance to start
        if self.__scroller:
            parts = self.__parts[:-1]
        else:
            parts = self.__parts

        # draw parts in reverse order
        parts.reverse()
        for part in parts:
            if region.rect_in(part.get_allocation()) != gtk.gdk.OVERLAP_RECTANGLE_OUT:
                self.__draw_part(cr, part, style, r, aw, shapes)
        parts.reverse()
        return

    def __draw_part(self, cr, part, style, r, aw, shapes, sxO=0):
        alloc = part.get_allocation()
        shape = part.shape
        state = part.state
        icon_pb = part.icon.pixbuf

        cr.save()
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
            aw,
            shapes)

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
        # otherwise, draw label
        if alloc.width == self.min_part_width and icon_pb:
            pass

        else:
            layout = part.get_layout()
            dst_x = alloc.x + margin - int(sxO)
            dst_y = (self.allocation.height - layout.get_pixel_size()[1])/2 + 1

            style.paint_layout(
                self.window,
                state,
                False,
                (dst_x, dst_y) + layout.get_pixel_size(),   # clip area
                self,
                None,
                dst_x,
                dst_y,
                layout)

        cr.restore()
        return

    def __draw_part_bg(self, cr, w, h, state, shape, style, r, aw, shapes):

        light = style.light[state]
        mid = style.mid[state]
        dark = style.dark[state]

        # make an active part look pressed in
        if state != gtk.STATE_ACTIVE:
            bevel = light
        else:
            bevel = mid

        # outer slight bevel or focal highlight
        shapes[shape](cr, 0, 0, w, h, r, aw, True)
        if not self.is_focus():
            cr.set_source_rgba(0, 0, 0, 0.055)
        else:
            sel = style.bg[gtk.STATE_SELECTED]
            cr.set_source_rgba(sel.red_float, sel.green_float, sel.blue_float, 0.65)
        cr.fill()
        cr.reset_clip()

        # bg linear vertical gradient
        shapes[shape](cr, 1, 1, w-1, h-1, r, aw)

        lin = cairo.LinearGradient(0, 0, 0, h-1)
        lin.add_color_stop_rgb(0, *rgb.lighten(mid, 0.18))
        lin.add_color_stop_rgb(1.0, mid.red_float, mid.green_float, mid.blue_float)
        cr.set_source(lin)
        cr.fill()

        # translate x,y by 0.5 so 1px lines are crisp
        cr.save()
        cr.translate(0.5, 0.5)
        cr.set_line_width(1.0)

        # strong outline
        shapes[shape](cr, 1, 1, w-2, h-2, r, aw)
        cr.set_source_rgb(
            dark.red_float,
            dark.green_float,
            dark.blue_float
            )
        cr.stroke()

        # inner bevel/highlight
        shapes[shape](cr, 2, 2, w-3, h-3, r, aw)
        cr.set_source_rgba(
            bevel.red_float,
            bevel.green_float,
            bevel.blue_float,
            0.65)
        cr.stroke()

        cr.restore()
        return

    def __shape_rect(self, cr, x, y, w, h, r, aw, focal_clip=False):
        global M_PI, PI_OVER_180
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def __shape_start_arrow(self, cr, x, y, w, h, r, aw, focal_clip=False):
        global M_PI, PI_OVER_180
        cr.new_sub_path()

        if focal_clip:
            cr.rectangle(0, 0, w-aw-1, h+1)
            cr.clip()

        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w, (h+y)*0.5)
        cr.line_to(w-aw, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def __shape_mid_arrow(self, cr, x, y, w, h, r, aw, focal_clip=False):

        if focal_clip:
            cr.rectangle(0, 0, w-aw-1, h+1)
            cr.clip()

        cr.move_to(-1, y)
        # arrow head
        cr.line_to(w-aw, y)
        cr.line_to(w, (h+y)*0.5)
        cr.line_to(w-aw, h)
        cr.line_to(-1, h)
        cr.close_path()
        return

    def __shape_end_cap(self, cr, x, y, w, h, r, aw, focal_clip=False):
        global M_PI, PI_OVER_180
        cr.move_to(-1, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(-1, h)
        cr.close_path()
        return

    def __state(self, part):
        # returns the idle state of the part depending on
        # whether part is active or not.
        if part == self.__active_part:
            return gtk.STATE_ACTIVE
        return gtk.STATE_NORMAL

    def __tooltip_check(self, part):
        # only show a tooltip if part is truncated, i.e. not all label text is
        # visible.
        if part.is_truncated():
            self.set_has_tooltip(False)
            gobject.timeout_add(50, self.__set_tooltip_cb, part.label)
        else:
            self.set_has_tooltip(False)
        return

    def __set_tooltip_cb(self, text):
        # callback allows the tooltip position to be updated as pointer moves
        # accross different parts
        self.set_has_tooltip(True)
        self.set_tooltip_text(text)
        return False

    def __motion_notify_cb(self, widget, event):
        if self.__scroll_xO > 0:
            return

        part = self.__part_at_xy(event.x, event.y)
        prev_focal = self.__focal_part

        if part and part.state != gtk.STATE_PRELIGHT:
            self.__tooltip_check(part)
            part.set_state(gtk.STATE_PRELIGHT)

            if prev_focal:
                prev_focal.set_state(self.__state(prev_focal))
                self.queue_draw_area(*prev_focal.allocation)

            self.__focal_part = part
            self.queue_draw_area(*part.allocation)

        elif part == None and prev_focal != None:
            prev_focal.set_state(self.__state(prev_focal))
            self.queue_draw_area(*prev_focal.allocation)
            self.__focal_part = None
        return

    def __leave_notify_cb(self, widget, event):
        prev_focal = self.__focal_part
        if prev_focal:
            prev_focal.set_state(self.__state(prev_focal))
            self.queue_draw_area(*prev_focal.allocation)
        self.__focal_part = None
        return

    def __button_press_cb(self, widget, event):
        part = self.__part_at_xy(event.x, event.y)
        if part:
            part.set_state(gtk.STATE_SELECTED)
            self.queue_draw_area(*part.allocation)
        return

    def __button_release_cb(self, widget, event):
        part = self.__part_at_xy(event.x, event.y)
        if part:
            self.grab_focus()
            part.emit("clicked", self)
            prev_active = self.set_active_part(part)

            self.queue_draw_area(*part.allocation)
            if prev_active:
                self.queue_draw_area(*prev_active.allocation)

        return

    def __key_release_cb(self, widget, event):
        part = None

        # left key pressed
        if event.keyval == 65363:
            part = self.get_left_part()

        # right key pressed
        elif event.keyval == 65361:
            part = self.get_right_part()

        if not part: return

        prev_active = self.set_active_part(part)
        self.queue_draw_area(*part.allocation)
        if prev_active:
            self.queue_draw_area(*prev_active.allocation)

        part.emit("clicked", event.copy())
        return

    def __expose_cb(self, widget, event):
        #t = gobject.get_current_time()
        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        if self.__scroll_xO:
            self.__draw_hscroll(cr)
        else:
            self.__draw_all(cr, event.area)

        del cr
        #print 'Exposure fps: %s' % (1 / (gobject.get_current_time() - t))
        return

    def __style_change_cb(self, widget, old_style):
        # when alloc.width == 1, this is typical of an unallocated widget,
        # lets not break a sweat for nothing...
        if self.allocation.width == 1:
            return

        settings = gtk.settings_get_default()
        self.animate = settings.get_property("gtk-enable-animations")

        # set height to 0 so that if part height has been reduced the widget will
        # shrink to an appropriate new height based on new font size
        self.set_size_request(-1, 0)

        parts = self.__parts
        self.__parts = []

        # recalc best fits, re-append then draw all
        for part in parts:

            if part.icon.pixbuf:
                part.icon.load_pixbuf()

            part.calc_best_fit()
            self.__append(part)

        self.queue_draw()
        return

    def __allocation_change_cb(self, widget, allocation):
        if allocation.width == 1:
            return

        path_w = self.__draw_width()
        if path_w == allocation.width:
            return
        elif path_w > allocation.width:
            self.__shrink_check(allocation)
        else:
            self.__grow_check(allocation.width, allocation)

        self.queue_draw()
        return


class PathPart(gobject.GObject):

    __gsignals__ = {
        "clicked": (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (PathBar,))
        }

    def __init__(self, label=None):
        gobject.GObject.__init__(self)

        self.__best_fit = (0,0)
        self.__layout = None
        self.__pbar = None

        self.allocation = [0, 0, 0, 0]
        self.state = gtk.STATE_NORMAL
        self.shape = SHAPE_RECTANGLE

        self.callback = None
        self.label = label or ''
        self.icon = Icon()
        return

    def set_callback(self, cb):
        self.callback = cb
        return

    def set_label(self, label):
        self.label = label
        return

    def set_icon(self, stock_icon, size):
        self.icon.specify(stock_icon, size)
        self.icon.load_pixbuf()
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

    def get_x(self):
        return self.allocation[0]

    def get_width(self):
        return self.allocation[2]

    def get_height(self):
        return self.allocation[3]

    def get_label(self):
        return self.label

    def get_allocation(self):
        return gtk.gdk.Rectangle(*self.allocation)

    def get_best_fit(self):
        return self.__best_fit

    def get_layout(self):
        return self.__layout

    def is_truncated(self):
        return self.__best_fit[0] != self.allocation[2]

    def calc_best_fit(self):
        pbar = self.__pbar

        # determine widget size base on label width
        self.__layout = self.__layout_text(self.label, pbar.get_pango_context())
        size = self.__layout.get_pixel_size()

        # calc text width + 2 * padding, text height + 2 * ypadding
        w = size[0] + 2*pbar.xpadding
        h = max(size[1] + 2*pbar.ypadding, pbar.get_size_request()[1])

        # if has icon add some more pixels on
        if self.icon.pixbuf:
            w += self.icon.pixbuf.get_width() + pbar.spacing
            h = max(self.icon.pixbuf.get_height() + 2*pbar.ypadding, h)

        # extend width depending on part shape  ...
        if self.shape == SHAPE_START_ARROW or self.shape == SHAPE_END_CAP:
            w += pbar.arrow_width

        elif self.shape == SHAPE_MID_ARROW:
            w += 2*pbar.arrow_width

        # if height greater than current height request,
        # reset height request to higher value
        # i get the feeling this should be in set_size_request(), but meh
        if h > pbar.get_size_request()[1]:
            pbar.set_size_request(-1, h)

        self.__best_fit = (w,h)
        return w, h

    def __layout_text(self, text, pango_context):
        # escape special characters
        text = gobject.markup_escape_text(text.strip())
        layout = pango.Layout(pango_context)
        layout.set_markup('<b>%s</b>' % text)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        return layout

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

    def __init__(self, name=None, size=None):
        self.name = name
        self.size = size
        self.pixbuf = None
        return

    def specify(self, name, size):
        self.name = name
        self.size = size
        return

    def load_pixbuf(self):
        if not self.name:
            print FAIL + 'Error: No icon specified.' + ENDC
            return
        if not self.size:
            print WARNING + 'Note: No icon size specified.' + ENDC

        style = gtk.Style()
        icon_set = style.lookup_icon_set(self.name)
        self.pixbuf = icon_set.render_icon(
            style,
            gtk.TEXT_DIR_NONE,
            gtk.STATE_NORMAL,
            self.size or gtk.ICON_SIZE_BUTTON,
            gtk.Image(),
            None)
        return


# gobject registration
gobject.type_register(PathPart)
gobject.type_register(PathBar)
