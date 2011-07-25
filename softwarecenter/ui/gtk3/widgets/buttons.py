from gi.repository import Gtk, Gdk, Pango, GObject, GdkPixbuf, PangoCairo
from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms, em
from softwarecenter.ui.gtk3.drawing import rounded_rect
from softwarecenter.ui.gtk3.widgets.stars import Star


_HAND = Gdk.Cursor.new(Gdk.CursorType.HAND2)


class Tile(Gtk.Button):

    MIN_WIDTH  = em(7)

    def __init__(self, label, icon, icon_size):
        Gtk.Button.__init__(self)
        self.set_focus_on_click(False)

        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.image_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL,
                                     StockEms.SMALL)

        self.add(self.box)

        if icon is not None:
            if isinstance(icon, GdkPixbuf.Pixbuf):
                self.image = Gtk.Image.new_from_pixbuf(icon)
            elif isinstance(icon, Gtk.Image):
                self.image = icon
            elif isinstance(icon, str):
                self.image = Gtk.Image.new_from_icon_name(icon, icon_size)
            else:
                msg = "Acceptable icon values: None, GdkPixbuf, GtkImage or str"
                raise TypeError, msg

            self.image_box.pack_start(self.image, True, True, 0)
            self.box.pack_start(self.image_box, True, True, 0)

        self.label = Gtk.Label.new(label)
        self.box.pack_start(self.label, True, True, 0)

        self.box.set_size_request(self.MIN_WIDTH, -1)
        self.set_relief(Gtk.ReliefStyle.NONE)
        return


class LabelTile(Tile):

    MIN_WIDTH = -1

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.MENU):
        Tile.__init__(self, label, iconname, icon_size)
        self.set_name("label-tile")
        self.label.set_line_wrap(True)
        return


class CategoryTile(Tile):

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG):
        Tile.__init__(self, label, iconname, icon_size)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_line_wrap(True)
        self.box.set_border_width(StockEms.SMALL)
        self.set_name("category-tile")
        return


class FeaturedTile(Tile):

    MAX_WIDTH = em(10)
    _MARKUP = '<b>%s</b>'

    def __init__(self, label, icon, review_stats, icon_size=48):
        Gtk.Button.__init__(self)
        self.set_focus_on_click(False)
        self._pressed = False

        self.box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, StockEms.MEDIUM)
        self.add(self.box)
        self.content_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, StockEms.MEDIUM)
        self.content_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, StockEms.SMALL)
        self.box.pack_start(self.content_left, False, False, 0)
        self.box.pack_start(self.content_right, False, False, 0)

        if isinstance(icon, GdkPixbuf.Pixbuf):
            self.image = Gtk.Image.new_from_pixbuf(icon)
        else:
            raise TypeError, "Expects a GdkPixbuf got %s" % type(icon)
        self.content_left.pack_start(self.image, False, False, 0)

        self.title = Gtk.Label.new(self._MARKUP % label)
        self.title.set_use_markup(True)
        self.title.set_alignment(0.0, 0.5)
        self.title.set_use_markup(True)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.content_right.pack_start(self.title, False, False, 0)

        self.category = Gtk.Label.new('<span font_desc="Italic %i">%s</span>' % (em(0.45), 'Category'))
        self.category.set_use_markup(True)
        self.category.set_alignment(0.0, 0.0)
        self.content_right.pack_start(self.category, False, False, 4)

        if review_stats is not None:
            self.stars = Star()
            self.stars.set_name("featured-star")
            self.stars.render_outline = True
            self.stars.set_rating(review_stats.ratings_average)
            self.content_right.pack_start(self.stars, False, False, 0)

            self.n_ratings = Gtk.Label.new('<span font_desc="Italic %i" color="%s">%i %s</span>' %
                                           (em(0.45), '#8C8C8C', review_stats.ratings_total, 'Reviews'))
            self.n_ratings.set_use_markup(True)
            self.n_ratings.set_alignment(0.0, 0.0)
            self.content_right.pack_start(self.n_ratings, False, False, 0)

        self.price = Gtk.Label.new('<span color="%s" font_desc="Bold %i">%s</span>' %
                                   ('#757575', em(0.6), 'FREE'))
        self.price.set_use_markup(True)
        self.content_left.pack_start(self.price, False, False, 0)

        self.set_relief(Gtk.ReliefStyle.NONE)
        self.set_name("featured-tile")

        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        return

    def do_get_preferred_width(self):
        return self.MAX_WIDTH, self.MAX_WIDTH

    def do_draw(self, cr):
        cr.save()
        A = self.get_allocation()
        if self._pressed:
            cr.translate(1, 1)

        if self.has_focus():
            Gtk.render_focus(self.get_style_context(),
                             cr,
                             3, 3,
                             A.width-6, A.height-6)

        for child in self: self.propagate_draw(child, cr)
        cr.restore()
        return

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)
        return True

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)
        self._pressed = False
        return True

    def on_press(self, widget, event):
        self._pressed = True
        return

    def on_release(self, widget, event):
        if not self._pressed: return
        self.emit("clicked")
        self._pressed = False
        return

#~ class _ChannelSelectorArrow(Gtk.Alignment):    
#~ 
    #~ def __init__(self):
        #~ Gtk.Alignment.__init__(self)
        #~ self.set(0.5, 1.0, 0.0, 0.0)
        #~ self.set_padding(1,1,1,1)
#~ 
        #~ self.onhover = False
#~ 
        #~ self.arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.IN)
        #~ self.add(self.arrow)
        #~ self.connect("draw", self.on_draw)
        #~ return
#~ 
    #~ def do_get_preferred_width(self):
        #~ pref_w, _ = self.arrow.get_preferred_width()
        #~ pref_w += sum(self.get_padding()[:2])
        #~ return pref_w, pref_w
#~ 
    #~ def set_onhover(self, is_onhover):
        #~ self.onhover = is_onhover
        #~ self.queue_draw()
#~ 
    #~ def on_draw(self, widget, cr):
        #~ a = widget.get_allocation()
        #~ rounded_rect(cr, 0.5, 0.5, a.width-1, a.height-1, 6)
        #~ 
        #~ if self.onhover and self.get_state_flags() == Gtk.StateFlags.PRELIGHT:
            #~ alpha = 0.3
        #~ else:
            #~ return
#~ 
        #~ context = self.get_style_context()
        #~ color = context.get_border_color(self.get_state_flags())
        #~ cr.set_source_rgba(color.red, color.green, color.blue, alpha)
        #~ cr.set_line_width(1)
        #~ cr.fill()
        #~ return


class SectionSelector(Tile):

    MIN_WIDTH  = em(5)
    _MARKUP = '<small>%s</small>'

    def __init__(self, label, iconname, icon_size=Gtk.IconSize.DIALOG,
                    has_channel_sel=False):
        markup = self._MARKUP % label
        Tile.__init__(self, markup, iconname, icon_size)
        self.set_size_request(-1, -1)
        self.set_name("channel-selector")
        self.label.set_use_markup(True)
        self.label.set_name("channel-selector")
        self.label.set_justify(Gtk.Justification.CENTER)

        self.has_channel_sel = has_channel_sel
        if not has_channel_sel: return

        self.channel_request_func = None
        self.popup = None
        self.radius = None

        self.channel_sel = Gtk.Arrow.new(Gtk.ArrowType.DOWN,
                                         Gtk.ShadowType.IN)
        self.channel_sel.set_name("channel-selector")
        filler = Gtk.Box()
        pref_w, _ = self.channel_sel.get_preferred_width()
        filler.set_size_request(pref_w, -1)

        self.image_box.pack_start(filler, False, False, 0)
        self.image_box.reorder_child(filler, 0)
        self.image_box.pack_start(self.channel_sel, False, False, 0)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)

        #~ self.connect("button-press-event", self.on_button_press)
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

    #~ def on_motion(self, button, event):
        #~ dd = self.channel_sel
        #~ dd_alloc = dd.get_allocation()
        #~ x, y = dd.get_pointer()
#~ 
        #~ # point in
        #~ if (x >= 0 and x <= dd_alloc.width and
            #~ y >= 0 and y <= dd_alloc.height):
            #~ if not dd.onhover:
                #~ dd.set_onhover(True)
#~ 
        #~ elif dd.onhover:
            #~ dd.set_onhover(False)
#~ 
        #~ return

    #~ def on_button_press(self, button, event):
        #~ dd = self.channel_sel
        #~ dd_alloc = dd.get_allocation()
        #~ x, y = dd.get_pointer()
#~ 
        #~ # point in
        #~ if (x >= 0 and x <= dd_alloc.width and
            #~ y >= 0 and y <= dd_alloc.height):
            #~ return True
        #~ return

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


class MoreLink(Gtk.EventBox):

    __gsignals__ = {
        "clicked" : (GObject.SignalFlags.RUN_LAST,
                     None, 
                     (),)
        }

    _MARKUP = '<span color="white"><b>%s</b></span>'
    _MORE = _("More")

    def __init__(self):
        Gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.label = Gtk.Label()
        self.label.set_markup(self._MARKUP % self._MORE)
        self.label.set_padding(StockEms.MEDIUM, 0)
        self.add(self.label)
        self._init_event_handling()
        return

    def do_draw(self, cr):
        cr.save()
        if self._pressed: cr.translate(1, 1)
        a = self.get_allocation()
        xo, yo = self.label.get_layout_offsets()

        xo -= a.x
        yo -= a.y

        cr.move_to(xo, yo+1)
        PangoCairo.layout_path(cr, self.label.get_layout())
        cr.set_source_rgb(0,0,0)
        cr.fill()

        Gtk.render_layout(self.get_style_context(),
                          cr, xo, yo, self.label.get_layout())
        cr.restore()
        return

    def _init_event_handling(self):
        self.set_property("can-focus", True)
        self._pressed = False
        self.set_events(Gdk.EventMask.BUTTON_RELEASE_MASK|
                        Gdk.EventMask.ENTER_NOTIFY_MASK|
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.connect("enter-notify-event", self.on_enter)
        self.connect("leave-notify-event", self.on_leave)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)

    def on_enter(self, widget, event):
        window = self.get_window()
        window.set_cursor(_HAND)
        return True

    def on_leave(self, widget, event):
        window = self.get_window()
        window.set_cursor(None)
        self._pressed = False
        self.queue_draw()
        return True

    def on_press(self, widget, event):
        self._pressed = True
        self.queue_draw()
        return

    def on_release(self, widget, event):
        if not self._pressed: return
        self.emit("clicked")
        self._pressed = False
        self.queue_draw()
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
