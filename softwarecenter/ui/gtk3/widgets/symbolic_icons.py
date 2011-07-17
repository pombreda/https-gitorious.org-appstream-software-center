import cairo

from math import pi as PI
from gi.repository import Gtk, Gdk, GObject

from softwarecenter.ui.gtk3.drawing import rounded_rect

# pi constants
_2PI = 2 * PI
PI_OVER_180 =   PI / 180


def radian(deg):
    return PI_OVER_180 * deg


class SymbolicIcon(Gtk.Image):

    SYMBOLIC_DIR = "softwarecenter/ui/gtk3/art/icons/"
    DROPSHADOW = "%s-dropshadow.png"
    ICON = "%s.png"

    def __init__(self, name):
        Gtk.Image.__init__(self)
        self.set_name("symbolic-icon")

        drop_shadow_path = self.SYMBOLIC_DIR + self.DROPSHADOW % name
        self.drop_shadow = cairo.ImageSurface.create_from_png(drop_shadow_path)
        icon_path = self.SYMBOLIC_DIR + self.ICON % name
        self.icon = cairo.ImageSurface.create_from_png(icon_path)

        self.drop_shadow_x_offset = 0
        self.drop_shadow_y_offset = 1

        self.connect("draw", self.on_draw, self.drop_shadow, self.icon,
                     self.drop_shadow_x_offset, self.drop_shadow_y_offset)
        return

    def do_get_preferred_width(self):
        ds = self.drop_shadow
        return ds.get_width(), ds.get_width()

    def do_get_preferred_height(self):
        ds = self.drop_shadow
        return ds.get_height(), ds.get_height()

    def on_draw(self, widget, cr, drop_shadow, icon, ds_xo, ds_yo, xo=0, yo=0):
        a = widget.get_allocation()

        # dropshadow
        x = (a.width - drop_shadow.get_width()) * 0.5 + ds_xo + xo
        y = (a.height - drop_shadow.get_height()) * 0.5 + ds_yo + yo
        cr.set_source_surface(drop_shadow, x, y)
        cr.paint_with_alpha(0.75)

        # colorised icon
        state = widget.get_state_flags()
        context = widget.get_style_context()
        color = context.get_color(state)
        Gdk.cairo_set_source_rgba(cr, color)
        x = (a.width - icon.get_width()) * 0.5 + xo
        y = (a.height - icon.get_height()) * 0.5 + yo
        cr.mask_surface(icon, x, y)
        return


class RotationAboutCenterAnimation(object):

    NEW_FRAME_DELAY = 50 # msec
    ROTATION_INCREMENT = radian(5) # 5 degrees -> radians

    def __init__(self):
        self.rotation = 0
        self.animator = None
        self._stop_requested = False

    def new_frame(self):
        _continue = True
        self.rotation += self.ROTATION_INCREMENT
        if self.rotation >= _2PI:
            self.rotation = 0
            if self._stop_requested:
                self.animator = None
                self._stop_requested = False
                _continue = False
        self.queue_draw()
        return _continue

    def start(self):
        if self.is_animating(): return
        self.animator = GObject.timeout_add(self.NEW_FRAME_DELAY,
                                            self.new_frame)
        return

    def stop(self):
        if not self.is_animating(): return
        self._stop_requested = True
        return

    def is_animating(self):
        return self.animator is not None


class PendingSymbolicIcon(SymbolicIcon, RotationAboutCenterAnimation):

    BUBBLE_BORDER_RADIUS = 5
    BUBBLE_XPADDING = 4
    BUBBLE_YPADDING = 0
    BUBBLE_FONT_DESC = "Bold 8.5"

    def __init__(self, name):
        SymbolicIcon.__init__(self, name)
        RotationAboutCenterAnimation.__init__(self)

        # for painting the trans count bubble
        self.layout = self.create_pango_layout("")
        self.transaction_count = 0
        return

    def on_draw(self, widget, cr, *args, **kwargs):
        cr.save()
        if self.is_animating():
            # translate to the center, then set the rotation
            a = widget.get_allocation()
            cr.translate(a.width * 0.5, a.height * 0.5)
            cr.rotate(self.rotation)
            # pass on the translation details
            kwargs['xo'] = -(a.width * 0.5)
            kwargs['yo'] = -(a.height * 0.5)

        # do icon drawing
        SymbolicIcon.on_draw(self, widget, cr, *args, **kwargs)
        cr.restore()

        if not self.is_animating() or not self.transaction_count: return
        # paint transactions bubble
        # get the layout extents and calc the bubble size
        ex = self.layout.get_pixel_extents()[1]
        x = (a.width - self.icon.get_width()) / 2 + self.icon.get_width() - ex.width + 2
        y = (a.height - self.icon.get_height()) / 2 + self.icon.get_height() - ex.height + 2
        w = ex.width + 2*self.BUBBLE_XPADDING
        h = ex.height + 2*self.BUBBLE_YPADDING
        # paint background
        rounded_rect(cr, x+1, y+1, w-2, h-2, self.BUBBLE_BORDER_RADIUS)
        cr.set_source_rgba(0,0,0,0.75)
        cr.fill()
        # paint outline
        #~ rounded_rect(cr, x+0.5, y+0.5, w-1, h-1, self.BUBBLE_BORDER_RADIUS)
        #~ cr.set_source_rgba(1,1,1, 0.85)
        #~ cr.set_line_width(1)
        #~ cr.stroke()
        # paint layout
        Gtk.render_layout(widget.get_style_context(), cr,
                          x + self.BUBBLE_XPADDING,
                          y + self.BUBBLE_YPADDING,
                          self.layout)
        return

    def set_transaction_count(self, count):
        if count == self.transaction_count: return
        self.transaction_count = count
        m = '<span font_desc="%s">%i</span>' % (self.BUBBLE_FONT_DESC,
                                                count)
        self.layout.set_markup(m, -1)
        self.queue_draw()
        return


if __name__ == "__main__":
    win = Gtk.Window()
    hb = Gtk.HBox(spacing=12)
    win.add(hb)
    ico = SymbolicIcon("available")
    hb.add(ico)
    ico = PendingSymbolicIcon("pending")
    ico.start()
    ico.set_transaction_count(33)
    hb.add(ico)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
