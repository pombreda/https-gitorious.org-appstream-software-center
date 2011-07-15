import cairo

from math import pi as PI
from gi.repository import Gtk, Gdk, GObject

# pi constants
_2PI = 2 * PI
PI_OVER_180 =   PI/180


def radian(deg):
    return PI_OVER_180 * deg


class SymbolicIcon(Gtk.Image):

    SYMBOLIC_DIR = "softwarecenter/ui/gtk3/art/icons/"
    DROPSHADOW = "%s-dropshadow.png"
    ICON = "%s.png"

    def __init__(self, name):
        Gtk.Image.__init__(self)

        drop_shadow_path = self.SYMBOLIC_DIR + self.DROPSHADOW % name
        self.drop_shadow = cairo.ImageSurface.create_from_png(drop_shadow_path)
        icon_path = self.SYMBOLIC_DIR + self.ICON % name
        self.icon = cairo.ImageSurface.create_from_png(icon_path)

        self.drop_shadow_x_offset = 0
        self.drop_shadow_y_offset = 1

        normal_rgb = Gdk.RGBA()
        active_rgb = Gdk.RGBA()
        normal_rgb.parse("#DBDBDB")    # light grey
        active_rgb.parse("#FFFFFF")    # white

        self.connect("draw", self.on_draw, self.drop_shadow, self.icon,
                     self.drop_shadow_x_offset, self.drop_shadow_y_offset,
                     normal_rgb, active_rgb)
        return

    def do_get_preferred_width(self):
        ds = self.drop_shadow
        return ds.get_width(), ds.get_width()

    def do_get_preferred_height(self):
        ds = self.drop_shadow
        return ds.get_height(), ds.get_height()

    def on_draw(self, widget, cr, drop_shadow, icon, ds_xo, ds_yo, normal_rgb, active_rgb, xo=0, yo=0):
        a = widget.get_allocation()

        # dropshadow
        x = (a.width - drop_shadow.get_width()) * 0.5 + ds_xo + xo
        y = (a.height - drop_shadow.get_height()) * 0.5 + ds_yo + yo
        cr.set_source_surface(drop_shadow, x, y)
        cr.paint()

        # colorised icon
        state = widget.get_state_flags()
        if state == Gtk.StateFlags.PRELIGHT or state == Gtk.StateFlags.ACTIVE:
            Gdk.cairo_set_source_rgba(cr, active_rgb)
        else:
            Gdk.cairo_set_source_rgba(cr, normal_rgb)
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

    def new_frame(self):
        self.rotation += self.ROTATION_INCREMENT
        if self.rotation >= _2PI:
            self.rotation = 0
        self.queue_draw()
        return True

    def start(self):
        if self.is_animating(): return
        self.animator = GObject.timeout_add(self.NEW_FRAME_DELAY,
                                            self.new_frame)
        return

    def stop(self):
        if not self.is_animating(): return
        GObject.source_remove(self.animator)
        self.rotation = 0
        self.queue_draw()
        return

    def is_animating(self):
        return self.animator is not None


class PendingSymbolicIcon(SymbolicIcon, RotationAboutCenterAnimation):

    def __init__(self, name):
        SymbolicIcon.__init__(self, name)
        RotationAboutCenterAnimation.__init__(self)
        self.transaction_count = 0
        return

    def on_draw(self, widget, cr, *args, **kwargs):
        if self.is_animating():
            a = widget.get_allocation()
            cr.translate(a.width * 0.5, a.height * 0.5)
            cr.rotate(self.rotation)
            kwargs['xo'] = -(a.width * 0.5)
            kwargs['yo'] = -(a.height * 0.5)
        SymbolicIcon.on_draw(self, widget, cr, *args, **kwargs)
        return

    def set_transaction_count(self, count):
        self.transaction_count = count
        return

if __name__ == "__main__":
    win = Gtk.Window()
    icon = "/home/matthew-dev/Projects/usc/lobby-aesthetics/softwarecenter/ui/gtk3/art/icons/available.png"
    drop_shadow = "/home/matthew-dev/Projects/usc/lobby-aesthetics/softwarecenter/ui/gtk3/art/icons/available-dropshadow.png"
    ico = SymbolicIcon(icon, drop_shadow)
    win.add(ico)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
