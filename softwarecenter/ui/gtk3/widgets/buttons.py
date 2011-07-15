from gi.repository import Gtk
from gi.repository import GObject

from softwarecenter.ui.gtk3.em import StockEms


class CategoryTile(Gtk.Button):

    MIN_WIDTH  = 130

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG):
        Gtk.Button.__init__(self)

        self.set_focus_on_click(False)

        vbox = Gtk.VBox()
        #~ vbox.set_border_width(StockEms.SMALL)
        self.add(vbox)

        image = Gtk.Image.new_from_icon_name(iconname, icon_size)
        vbox.add(image)

        label = Gtk.Label.new(label)
        label.set_alignment(0.5, 0.0)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        vbox.add(label)

        self.set_size_request(self.MIN_WIDTH, -1)
        self.set_relief(Gtk.ReliefStyle.NONE)


class Link(Gtk.Label):

    __gsignals__ = {
        "clicked" : (GObject.SignalFlags.RUN_LAST,
                     None, 
                     (),)
        }

    def __init__(self, markup="", uri="none"):
        Gtk.Label.__init__(self)
        self.set_markup('<a href="%s">%s</a>' % (uri, markup))
        self.connect("activate-link", self.on_activate_link)
        return

    def on_activate_link(self, uri, data):
        self.emit("clicked")
        return


if __name__ == "__main__":
    win = Gtk.Window()
    win.set_size_request(200,200)

    vb = Gtk.VBox(spacing=12)
    win.add(vb)

    link = Link("<small>test link</small>", uri="www.google.co.nz")
    vb.add(link)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
