import gtk
import cairo
import gobject


# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295


def rounded_rect(cr, x, y, w, h, r):
    global M_PI, PI_OVER_180
    cr.new_sub_path()
    cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
    cr.arc(w-r+x, r+y, r, 270*PI_OVER_180, 0)
    cr.arc(w-r+x, h-r+y, r, 0, 90*PI_OVER_180)
    cr.arc(r+x, h-r+y, r, 90*PI_OVER_180, M_PI)
    cr.close_path()
    return


class FancyProgress(gtk.DrawingArea):

    def __init__(self):
        gtk.DrawingArea.__init__(self)

        self.fraction = 0.5
        self.text = None
        self.frame = gtk.gdk.pixbuf_new_from_file('data/misc/progress-shad.png')
        self.connect('expose-event', self.on_expose_cb)
        return

    def set_text(self, text):
        self.text = text
        self.queue_draw()
        return

    def set_fraction(self, fraction):
        self.fraction = fraction
        self.queue_draw()
        return

    def on_expose_cb(self, widget, event):
        alloc = widget.get_allocation()
        aw, ah = alloc.width, alloc.height
        if not (aw > 1 and ah > 1): return

        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        # bg
        lin = cairo.LinearGradient(0, 0, 0, ah)
        lin.add_color_stop_rgb(1, 0.2235, 0.2392, 0.2941)
        lin.add_color_stop_rgb(0, 0.2863, 0.3176, 0.3843)
        cr.set_source(lin)
        rounded_rect(cr, 0, 0, aw, ah, 3)
        cr.fill()

        w, h = self.frame.get_width(), self.frame.get_height()
        x = (aw - w)/2
        y = (ah - h)/2

        # slight highlight
        cr.save()
        cr.translate(0.5,0.5)
        cr.set_line_width(1)
        rounded_rect(cr, x-1, y-1, w+1, h+1, 5)
        cr.set_source_rgba(1,1,1, 0.05)
        cr.stroke()
        cr.restore()

        cr.rectangle(x,y,w*self.fraction, h)
        cr.clip()

        rounded_rect(cr, x, y, w, h, 5)

        c = gtk.gdk.color_parse("#FFA500")
        cr.set_source_rgb(c.red_float, c.green_float, c.blue_float)
        cr.fill()

        cr.reset_clip()

        cr.set_source_pixbuf(self.frame, x, y)
        cr.paint()

        # draw text
        if not self.text:
            del cr
            return

        import pango
        layout = pango.Layout(self.get_pango_context())
        layout.set_text(self.text)
        layout.set_ellipsize(pango.ELLIPSIZE_END)
        layout.set_width(w*pango.SCALE)

        dst_x = (aw - layout.get_pixel_size()[0])/2
        dst_y = int(y - 2.5*h)
        w, h = layout.get_pixel_size()
        self.style.paint_layout(
            self.window,
            gtk.STATE_SELECTED,
            False,
            (dst_x, dst_y, w+4, h),   # clip area
            self,
            None,
            dst_x,
            dst_y,
            layout)

        del cr
        return



class FancyImage(gtk.DrawingArea):

    BORDER_WIDTH = 25

    DROPSHADOW_CORNERS = {
        'nw': gtk.gdk.pixbuf_new_from_file('data/misc/nw.png'),
        'ne': gtk.gdk.pixbuf_new_from_file('data/misc/ne.png'),
        'sw': gtk.gdk.pixbuf_new_from_file('data/misc/sw.png'),
        'se': gtk.gdk.pixbuf_new_from_file('data/misc/se.png')
        }

    def __init__(self):
        gtk.DrawingArea.__init__(self)

        self.pixbuf = None
        self._animator = None

        self.connect('expose-event', self.on_expose_cb)
        return

    def set_from_file(self, path):
        # if there is an animation kill the handler
        if self._animator:
            gobject.source_remove(self._animator)
        if not path:
            return False

        im_data = self.load_image(path)
        self.display_image(im_data)
        return

    def load_image(self, path):
        pic = gtk.gdk.PixbufAnimation(path)
        pb = pic.get_static_image()

        w, h = pb.get_width(), pb.get_height()
        w += 2*self.BORDER_WIDTH
        h += 2*self.BORDER_WIDTH
        self.set_size_request(w, h)

        if pic.is_static_image():
            pb_iter = None
        else:
            pb_iter = pic.get_iter()

        return pb, pb_iter

    def display_image(self, im_data):
        pb, pb_iter, = im_data
        self.pixbuf = pb
        self.queue_draw()

        if pb_iter:
            # if animation; start animation

            # calc draw area
            self._animator = gobject.timeout_add(
                pb_iter.get_delay_time(),
                self.advance_cb,
                pb_iter)
        return

    def draw_image(self, cr, pb, x, y, w, h):
        # draw dropshadow
        self.draw_dropshadow(cr, x-1, y-1, w+2, h+2)

        # draw image frame
        cr.rectangle(x-1, y-1, w+2, h+2)
        cr.set_source_rgb(1,1,1)
        cr.fill()

        # redraw old image
        cr.set_source_pixbuf(pb, x, y)
        cr.paint()
        return

    def draw_dropshadow(self, cr, x, y, sw, sh):
        cr.set_line_width(1)

        # n shadow
        xO, x1 = x+2, x+sw-2
        self.line(cr,0.0667,xO,y-0.5,x1,y-0.5)
        self.line(cr,0.0196,xO,y-1.5,x1,y-1.5)

        # s shadow
        xO += 2
        x1 -= 2
        yO = y+sh+0.5
        self.line(cr,0.6824,xO,yO,x1,yO)
        self.line(cr,0.5216,xO,yO+1,x1,yO+1)
        self.line(cr,0.3294,xO,yO+2,x1,yO+2)
        self.line(cr,0.1686,xO,yO+3,x1,yO+3)
        self.line(cr,0.0667,xO,yO+4,x1,yO+4)
        self.line(cr,0.0196,xO,yO+5,x1,yO+5)

        # e shadow
        xO, yO, y1  = x+sw+0.5, y+5, y+sh-2
        self.line(cr,0.3294,xO,yO,xO,y1)
        self.line(cr,0.1686,xO+1,yO,xO+1,y1)
        self.line(cr,0.0667,xO+2,yO,xO+2,y1)
        self.line(cr,0.0196,xO+3,yO,xO+3,y1)

        # w shadow
        xO = x-0.5
        self.line(cr,0.3294,xO,yO,xO,y1)
        self.line(cr,0.1686,xO-1,yO,xO-1,y1)
        self.line(cr,0.0667,xO-2,yO,xO-2,y1)
        self.line(cr,0.0196,xO-3,yO,xO-3,y1)

        # corner shadows from cached pixbufs
        cnrs = self.DROPSHADOW_CORNERS
        cr.set_source_pixbuf(cnrs['nw'], x-4, y-2)
        cr.paint()
        cr.set_source_pixbuf(cnrs['ne'], x+sw-2, y-2)
        cr.paint()
        cr.set_source_pixbuf(cnrs['sw'], x-4, y+sh-2)
        cr.paint()
        cr.set_source_pixbuf(cnrs['se'], x+sw-4, y+sh-2)
        cr.paint()
        return

    def line(self, cr, a, x0, y0, x1, y1):
        # just a plain old line
        cr.set_source_rgba(0,0,0,a)
        cr.move_to(x0,y0)
        cr.line_to(x1,y1)
        cr.stroke()
        return

    def on_expose_cb(self, widget, event):
        cr = widget.window.cairo_create()
        cr.rectangle(event.area)
        cr.clip()

        alloc = widget.get_allocation()
        aw, ah = alloc.width, alloc.height

        # bg
        lin = cairo.LinearGradient(0, 0, 0, ah)
        lin.add_color_stop_rgb(1, 0.2235, 0.2392, 0.2941)
        lin.add_color_stop_rgb(0, 0.2863, 0.3176, 0.3843)
        cr.set_source(lin)
        rounded_rect(cr, 0, 0, aw, ah, 3)
        cr.fill()

        if aw > 1 and ah > 1 and self.pixbuf:
            w, h = self.pixbuf.get_width(), self.pixbuf.get_height()
            x = (aw - w)/2
            y = (ah - h)/2
            self.draw_image(cr, self.pixbuf, x, y, w, h)

        del cr
        return

    def on_change_cb(self, imstore):
        self.set_image(imstore.get_path())
        return

    def advance_cb(self, pb_iter):
        self.pixbuf = pb_iter.get_pixbuf()
        pb_iter.advance()
        self.queue_draw()
        return True
