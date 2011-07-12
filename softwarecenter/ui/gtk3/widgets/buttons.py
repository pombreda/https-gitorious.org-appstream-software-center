from gi.repository import Gtk
from gi.repository import GObject

from softwarecenter.ui.gtk3.em import StockEms


class Tile(Gtk.Button):

    MIN_WIDTH  = 130

    def __init__(self, label, iconname, icon_size):
        Gtk.Button.__init__(self)
        self.set_focus_on_click(False)

        self.vbox = Gtk.VBox(spacing=StockEms.SMALL)
        #~ self.vbox.set_border_width(StockEms.SMALL)
        self.add(self.vbox)
        image = Gtk.Image.new_from_icon_name(iconname, icon_size)
        self.vbox.add(image)

        label = Gtk.Label.new(label)
        label.set_alignment(0.5, 0.0)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        self.vbox.add(label)

        self.set_size_request(self.MIN_WIDTH, -1)
        self.set_relief(Gtk.ReliefStyle.NONE)
        return



class CategoryTile(Tile):

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG):
        Tile.__init__(self, label, iconname, icon_size)
        self.set_name("category-tile")
        return


class SectionSelector(Tile):

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG,
                    has_channel_sel=True):
        Tile.__init__(self, label, iconname, icon_size)
        self.set_size_request(-1, -1)

        self.has_channel_sel = has_channel_sel
        self.channel_request_func = None
        if not has_channel_sel: return

        self.channel_sel = Gtk.Button()
        self.channel_sel.set_relief(Gtk.ReliefStyle.NONE)
        arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.IN)
        self.channel_sel.add(arrow)
        self.vbox.pack_start(self.channel_sel, False, False, 0)

        self.connect("button-press-event", self.on_button_press,
                     has_channel_sel)
        self.connect('button-release-event', self.on_button_release,
                     has_channel_sel)
        return

    def on_button_press(self, button, event, has_channel_sel):
        if not has_channel_sel: return

        dd = self.channel_sel
        dd_alloc = dd.get_allocation()
        x, y = dd.get_pointer()

        # point in
        if (x >= 0 and x <= dd_alloc.width and
            y >= 0 and y <= dd_alloc.height):
            return True
        return

    def on_button_release(self, button, event, has_channel_sel):
        if not has_channel_sel: return
        if self.channel_request_func is None:
            raise AttributeError, 'No "channel_request_func" set!'

        dd = self.channel_sel
        dd_alloc = dd.get_allocation()
        x, y = dd.get_pointer()

        # point in
        if (x >= 0 and x <= dd_alloc.width and
            y >= 0 and y <= dd_alloc.height):
            self.show_channel_sel_popup(self, event)
            return True
        self.emit("clicked")
        return

    def show_channel_sel_popup(self, widget, event):

        def position_func(menu, (window, a)):
            menu_alloc = menu.get_allocation()
            x, y = window.get_root_coords(a.x, a.y + a.height)
            return (x, y, False)

        a = widget.get_allocation()
        window = widget.get_window()

        popup = Gtk.Menu()
        self.channel_request_func(popup)

        popup.attach_to_widget(widget, None)
        popup.set_size_request(150, -1)
        popup.popup(None, None, position_func, (window, a),
                    event.button, event.time)
        return

    def set_channel_request_func(self, func):
        self.channel_request_func = func
        return


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
