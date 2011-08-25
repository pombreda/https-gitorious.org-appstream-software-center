from gi.repository import Gtk


class HBar(Gtk.VBox):

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.set_size_request(-1, 1)
        return

    def do_draw(self, cr):
        cr.save()
        a = self.get_allocation()
        cr.move_to(0,0)
        cr.rel_line_to(a.width, 0)
        cr.set_source_rgb(0.784313725, 0.784313725, 0.784313725)
        cr.set_dash((1, 2), 1)
        cr.stroke()
        cr.restore()
        return
