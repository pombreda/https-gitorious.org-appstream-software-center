# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import cairo

from gi.repository import Gtk, Gdk, Pango, GObject, GdkPixbuf, PangoCairo
from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms, em
from softwarecenter.ui.gtk3.widgets.stars import Star


_HAND = Gdk.Cursor.new(Gdk.CursorType.HAND2)


def _parse_icon(icon, icon_size):
    if isinstance(icon, GdkPixbuf.Pixbuf):
        image = Gtk.Image.new_from_pixbuf(icon)
    elif isinstance(icon, Gtk.Image):
        image = icon
    elif isinstance(icon, str):
        image = Gtk.Image.new_from_icon_name(icon, icon_size)
    else:
        msg = "Acceptable icon values: None, GdkPixbuf, GtkImage or str"
        raise TypeError(msg)
    return image


class _Tile(object):

    MIN_WIDTH  = em(7)

    def __init__(self):
        self.set_focus_on_click(False)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        self.box.set_size_request(self.MIN_WIDTH, -1)
        self.add(self.box)
        return

    def build_default(self, label, icon, icon_size):
        if icon is not None:
            self.image = _parse_icon(icon, icon_size)
            self.box.pack_start(self.image, True, True, 0)

        self.label = Gtk.Label.new(label)
        self.box.pack_start(self.label, True, True, 0)
        return

class TileButton(Gtk.Button, _Tile):

    def __init__(self):
        Gtk.Button.__init__(self)
        _Tile.__init__(self)
        return


class TileToggleButton(Gtk.RadioButton, _Tile):

    def __init__(self):
        Gtk.RadioButton.__init__(self)
        self.set_mode(False)
        _Tile.__init__(self)
        return


class LabelTile(TileButton):

    MIN_WIDTH = -1

    def __init__(self, label, icon, icon_size=Gtk.IconSize.MENU):
        TileButton.__init__(self)
        self.build_default(label, icon, icon_size)
        self.set_name("label-tile")
        self.label.set_line_wrap(True)
        return


class CategoryTile(TileButton):

    def __init__(self, label, icon, icon_size=Gtk.IconSize.DIALOG):
        TileButton.__init__(self)
        self.build_default(label, icon, icon_size)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_line_wrap(True)
        self.box.set_border_width(StockEms.SMALL)
        self.set_name("category-tile")
        return


class FeaturedTile(TileButton):

    MAX_WIDTH = em(10)
    _MARKUP = '<b>%s</b>'

    def __init__(self, label, icon, review_stats, category=None, icon_size=48):
        TileButton.__init__(self)
        self._pressed = False

        self.box.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.box.set_spacing(StockEms.MEDIUM)

        self.content_left = Gtk.Box.new(Gtk.Orientation.VERTICAL, StockEms.MEDIUM)
        self.content_right = Gtk.Box.new(Gtk.Orientation.VERTICAL, StockEms.SMALL)
        self.box.pack_start(self.content_left, False, False, 0)
        self.box.pack_start(self.content_right, False, False, 0)
        self.image = _parse_icon(icon, icon_size)
        self.content_left.pack_start(self.image, False, False, 0)

        self.title = Gtk.Label.new(self._MARKUP % label)
        self.title.set_alignment(0.0, 0.5)
        self.title.set_use_markup(True)
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.content_right.pack_start(self.title, False, False, 0)

        if category is not None:
            self.category = Gtk.Label.new('<span font_desc="Italic %i">%s</span>' % (em(0.45), category))
            self.category.set_use_markup(True)
            self.category.set_alignment(0.0, 0.0)
            self.category.set_ellipsize(Pango.EllipsizeMode.END)
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


class ChannelSelector(Gtk.Button):

    PADDING = 0

    def __init__(self, section_button):
        Gtk.Button.__init__(self)
        alignment = Gtk.Alignment.new(0.5, 0.5, 0.0, 1.0)
        alignment.set_padding(self.PADDING, self.PADDING,
                              self.PADDING, self.PADDING)
        self.add(alignment)
        self.arrow = Gtk.Arrow.new(Gtk.ArrowType.DOWN, Gtk.ShadowType.IN)
        alignment.add(self.arrow)
        self.set_name("section-selector")
        self.arrow.set_name("section-selector")

        self.section_button = section_button
        self.popup = None
        self.connect("button-press-event", self.on_button_press)
        return

    def do_draw(self, cr):
        a = self.get_allocation()
        cr.set_line_width(1)
        cr.rectangle(-0.5, -1.5, a.width, a.height+3)
        cr.set_source_rgba(0,0,0, 0.6)
        cr.stroke()
        cr.rectangle(0.5, -1.5, a.width-2, a.height+3)
        cr.set_source_rgba(1,1,1, 0.07)
        cr.stroke()

        for child in self: self.propagate_draw(child, cr)
        return

    def on_button_press(self, button, event):
        if self.popup is None:
            self.build_channel_selector()
        self.show_channel_sel_popup(self, event)
        return

    def show_channel_sel_popup(self, widget, event):

        def position_func(menu, (window, a)):
            x, y = window.get_root_coords(a.x,
                                          a.y + a.height)
            return (x, y, False)

        a = self.section_button.get_allocation()
        window = self.section_button.get_window()
        self.popup.popup(None, None, position_func, (window, a),
                         event.button, event.time)
        return

    def set_build_func(self, build_func):
        self.build_func = build_func
        return

    def build_channel_selector(self):
        self.popup = Gtk.Menu()
        self.build_func(self.popup)
        self.popup.attach_to_widget(self, None)
        return


class SectionSelector(TileToggleButton):

    MIN_WIDTH  = em(5)
    _MARKUP = '<small>%s</small>'

    def __init__(self, label, icon, icon_size=Gtk.IconSize.DIALOG):
        TileToggleButton.__init__(self)
        markup = self._MARKUP % label
        self.build_default(markup, icon, icon_size)
        self.label.set_use_markup(True)
        self.label.set_justify(Gtk.Justification.CENTER)
        self.label.set_name("section-selector")
        self.set_name("section-selector")
        self.draw_hint_has_channel_selector = False
        self.label.connect("draw", self.on_label_draw)
        return

    def do_draw(self, cr):
        a = self.get_allocation()
        if self.get_active():
            cr.rectangle(0, -1, a.width, a.height+2)
            lin = cairo.LinearGradient(0, 0, 0, a.height)
            lin.add_color_stop_rgba(0.0, 0,0,0, 0.0)
            lin.add_color_stop_rgba(0.25, 0,0,0, 0.3)
            lin.add_color_stop_rgba(0.5, 0,0,0, 0.5)
            lin.add_color_stop_rgba(0.75, 0,0,0, 0.3)
            lin.add_color_stop_rgba(1.0, 0,0,0, 0.0)
            cr.set_source(lin)
            cr.fill_preserve()
            cr.set_source_rgba(0,0,0, 0.6)
            cr.stroke()

        elif self.draw_hint_has_channel_selector:
            cr.set_line_width(1)
            cr.move_to(a.width-0.5, -1)
            cr.rel_line_to(0, a.height+2)
            cr.set_source_rgba(0,0,0,0.6)
            cr.stroke()

        for child in self: 
            self.propagate_draw(child, cr)
        return

    def on_label_draw(self, label, cr):
        layout = label.get_layout()

        a = self.label.get_allocation()
        x, y = label.get_layout_offsets()
        x -= a.x
        y -= a.y

        cr.move_to(x, y+1)
        PangoCairo.layout_path(cr, layout)
        cr.set_source_rgba(0,0,0,0.3)
        cr.set_line_width(2.5)
        cr.stroke()

        context = self.get_style_context()
        context.set_state(self.get_state_flags())
        Gtk.render_layout(context, cr, x, y, layout)
        return True


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
    
    def clicked(self):
        self.emit("clicked")

def get_test_buttons_window():
    win = Gtk.Window()
    win.set_size_request(200,200)

    vb = Gtk.VBox(spacing=12)
    win.add(vb)

    link = Link("<small>test link</small>", uri="www.google.co.nz")
    vb.add(link)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    win = get_test_buttons_window()
    Gtk.main()
