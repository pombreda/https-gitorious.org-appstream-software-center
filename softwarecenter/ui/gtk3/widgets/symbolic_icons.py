import cairo

from gi.repository import Gtk, Gdk


class SymbolicIcon(Gtk.Misc):

    def __init__(self, icon_path, drop_shadow_path):
        Gtk.Misc.__init__(self)

        self.drop_shadow = cairo.ImageSurface.create_from_png(drop_shadow_path)
        self.icon = cairo.ImageSurface.create_from_png(icon_path)

        self.drop_shadow_x_offset = 0
        self.drop_shadow_y_offset = 0

        self.connect("draw", self.on_draw, self.drop_shadow, self.icon,
                     self.drop_shadow_x_offset, self.drop_shadow_y_offset)
        return

    def do_get_preferred_width(self):
        ds = self.drop_shadow
        return ds.get_width(), ds.get_width()

    def do_get_preferred_height(self):
        ds = self.drop_shadow
        return ds.get_height(), ds.get_height()

    def on_draw(self, widget, cr, drop_shadow, icon, ds_xo, ds_yo):
        a = widget.get_allocation()

        # dropshadow
        x = (a.width - drop_shadow.get_width()) * 0.5 + ds_xo
        y = (a.height - drop_shadow.get_height()) * 0.5 + ds_yo
        cr.set_source_surface(drop_shadow, x, y)
        cr.paint_with_alpha(0.5)

        # colorised icon
        x = (a.width - icon.get_width()) * 0.5
        y = (a.height - icon.get_height()) * 0.5
        cr.set_source_rgb(1,1,1)
        cr.mask_surface(icon, x, y)
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
