from gi.repository import Gtk, Gdk, GObject

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.drawing import rounded_rect, rounded_rect2


class Tile(Gtk.Button):

    MIN_WIDTH  = 130

    def __init__(self, label, icon, icon_size):
        Gtk.Button.__init__(self)
        self.set_focus_on_click(False)

        self.vbox = Gtk.VBox(spacing=StockEms.SMALL)
        self.image_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL,
                                     StockEms.SMALL)

        self.add(self.vbox)

        if isinstance(icon, Gtk.Image):
            self.image = icon
        elif isinstance(icon, str):
            self.image = Gtk.Image.new_from_icon_name(icon, icon_size)

        self.image_box.pack_start(self.image, True, True, 0)
        self.vbox.pack_start(self.image_box, False, False, 0)

        label = Gtk.Label.new(label)
        label.set_alignment(0.5, 0.0)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        self.vbox.pack_start(label, False, False, 0)

        self.set_size_request(self.MIN_WIDTH, -1)
        self.set_relief(Gtk.ReliefStyle.NONE)
        return


class CategoryTile(Tile):

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG):
        Tile.__init__(self, label, iconname, icon_size)
        self.set_border_width(StockEms.MEDIUM)
        self.set_name("category-tile")
        return


class _ChannelSelectorArrow(Gtk.Alignment):    

    def __init__(self):
        Gtk.Alignment.__init__(self)
        self.set(0.5, 1.0, 0.0, 0.0)
        self.set_padding(1,1,1,1)

        self.onhover = False

        self.arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.IN)
        self.add(self.arrow)
        self.connect("draw", self.on_draw)
        return

    def do_get_preferred_width(self):
        pref_w, _ = self.arrow.get_preferred_width()
        pref_w += sum(self.get_padding()[:2])
        print pref_w
        return pref_w, pref_w

    def set_onhover(self, is_onhover):
        self.onhover = is_onhover
        self.queue_draw()

    def on_draw(self, widget, cr):
        a = widget.get_allocation()
        rounded_rect(cr, 0.5, 0.5, a.width-1, a.height-1, 6)
        
        if self.onhover and self.get_state_flags() == Gtk.StateFlags.PRELIGHT:
            alpha = 0.3
        else:
            return

        context = self.get_style_context()
        color = context.get_border_color(self.get_state_flags())
        cr.set_source_rgba(color.red, color.green, color.blue, alpha)
        cr.set_line_width(1)
        cr.fill()
        return


class SectionSelector(Tile):

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG,
                    has_channel_sel=False):
        Tile.__init__(self, label, iconname, icon_size)
        self.set_size_request(-1, -1)

        self.has_channel_sel = has_channel_sel
        self.channel_request_func = None
        if not has_channel_sel: return

        self.popup = None
        self.radius = None

        self.channel_sel = _ChannelSelectorArrow()
        filler = Gtk.Box()
        pref_w, _ = self.channel_sel.get_preferred_width()
        filler.set_size_request(pref_w, -1)

        self.image_box.pack_start(filler, False, False, 0)
        self.image_box.reorder_child(filler, 0)
        self.image_box.pack_start(self.channel_sel, False, False, 0)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        self.connect("button-press-event", self.on_button_press)
        self.connect('button-release-event', self.on_button_release)
        #~ self.connect('motion-notify-event', self.on_motion)
        self.connect("draw", self.on_draw)
        return

    def on_draw(self, widget, cr):
        if self.popup is None or not self.popup.get_visible(): return

        a = self.get_allocation()
        context = self.get_style_context()
        color = context.get_border_color(self.get_state_flags())

        rounded_rect(cr, 0, 0, a.width, a.height, self.radius)
        Gdk.cairo_set_source_rgba(cr, color)
        #~ cr.set_line_width(1)
        cr.fill()
        return

    def on_motion(self, button, event):
        dd = self.channel_sel
        dd_alloc = dd.get_allocation()
        x, y = dd.get_pointer()

        # point in
        if (x >= 0 and x <= dd_alloc.width and
            y >= 0 and y <= dd_alloc.height):
            if not dd.onhover:
                dd.set_onhover(True)

        elif dd.onhover:
            dd.set_onhover(False)

        return

    def on_button_press(self, button, event):
        #~ dd = self.channel_sel
        #~ dd_alloc = dd.get_allocation()
        #~ x, y = dd.get_pointer()
#~ 
        #~ # point in
        #~ if (x >= 0 and x <= dd_alloc.width and
            #~ y >= 0 and y <= dd_alloc.height):
            #~ return True
        return

    def on_button_release(self, button, event):
        #~ dd = self.channel_sel
        #~ dd_alloc = dd.get_allocation()
        #~ x, y = dd.get_pointer()
#~ 
        #~ # point in
        #~ if (x >= 0 and x <= dd_alloc.width and
            #~ y >= 0 and y <= dd_alloc.height):
        if self.popup is None:
            self.build_channel_selector()
        self.show_channel_sel_popup(self, event)
            #~ return True
        #~ self.emit("clicked")
        return

    def on_popup_hide(self, widget):
        self.queue_draw()

    def show_channel_sel_popup(self, widget, event):

        def position_func(menu, (window, a)):
            menu_alloc = menu.get_allocation()
            x, y = window.get_root_coords(a.x,
                                          a.y + a.height - self.radius)
            return (x, y, False)

        a = widget.get_allocation()
        window = widget.get_window()

        if self.radius is None:
            state = self.get_state_flags()
            context = self.get_style_context()
            self.radius = context.get_property("border-radius", state)

        self.popup.popup(None, None, position_func, (window, a),
                         event.button, event.time)
        return

    def set_build_func(self, build_func):
        self.build_func = build_func
        return

    def build_channel_selector(self):
        self.popup = Gtk.Menu()
        self.build_func(self.popup)
        self.popup.attach_to_widget(self.channel_sel, None)
        self.popup.connect("hide", self.on_popup_hide)
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
