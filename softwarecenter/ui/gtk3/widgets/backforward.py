# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from gi.repository import Atk
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from gettext import gettext as _

from softwarecenter.ui.gtk3.drawing import rounded_rect, darken

DEFAULT_PART_SIZE = (28, -1)


class BackForwardButton(Gtk.HBox):

    __gsignals__ = {'left-clicked':(GObject.SignalFlags.RUN_LAST,
                                    None,
                                    ()),

                    'right-clicked':(GObject.SignalFlags.RUN_LAST,
                                    None,
                                    ())}

    BORDER_RADIUS = 4

    def __init__(self, part_size=None):
        Gtk.HBox.__init__(self)
        self.set_spacing(1)

        if self.get_direction() != Gtk.TextDirection.RTL:
            # ltr
            self.left = Left('left-clicked')
            self.right = Right('right-clicked')
            self.set_button_atk_info_ltr()
        else:
            # rtl
            self.left = Right('left-clicked', arrow_type=Gtk.ArrowType.LEFT)
            self.right = Left('right-clicked', arrow_type=Gtk.ArrowType.RIGHT)
            self.set_button_atk_info_rtl()

        atk_obj = self.get_accessible()
        atk_obj.set_name(_('History Navigation'))
        atk_obj.set_description(_('Navigate forwards and backwards.'))
        atk_obj.set_role(Atk.Role.PANEL)

        self.pack_start(self.left, True, True, 0)
        self.pack_end(self.right, True, True, 0)

        self.left.connect("clicked", self.on_clicked)
        self.right.connect("clicked", self.on_clicked)
        return

    def on_clicked(self, button):
        self.emit(button.signal_name)
        return
 
    def do_draw(self, cr):
        cr.save()
        a = self.get_allocation()
        # divider
        toolbar = self.get_ancestor('GtkToolbar')
        context = toolbar.get_style_context()

        color = darken(context.get_border_color(Gtk.StateFlags.ACTIVE), 0.2)

        Gdk.cairo_set_source_rgba(cr, color)
        cr.move_to(0.5*a.width, 1)
        cr.rel_line_to(0, a.height-2)
        cr.set_line_width(1)
        cr.stroke()

        cr.restore()

        for child in self: self.propagate_draw(child, cr)
        return

    def set_button_atk_info_ltr(self):
        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))

        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        return

    def set_button_atk_info_rtl(self):
        # right button
        atk_obj = self.right.get_accessible()
        atk_obj.set_name(_('Back Button'))
        atk_obj.set_description(_('Navigates back.'))
        atk_obj.set_role(Atk.Role.PUSH_BUTTON)

        # left button
        atk_obj = self.left.get_accessible()
        atk_obj.set_name(_('Forward Button'))
        atk_obj.set_description(_('Navigates forward.'))
        atk_obj.set_role(Atk.Role.PUSH_BUTTON)
        return

    def set_use_hand_cursor(self, use_hand):
        self.use_hand = use_hand
        return


class ButtonPart(Gtk.Button):

    def __init__(self, arrow_type, signal_name):
        Gtk.Button.__init__(self)
        #~ self.set_name("backforward")
        self.set_relief(Gtk.ReliefStyle.NORMAL)
        self.arrow_type = arrow_type

        if self.arrow_type == Gtk.ArrowType.LEFT:
            arrow = Gtk.Image.new_from_icon_name('stock_left',
                                                 Gtk.IconSize.BUTTON)
        elif self.arrow_type == Gtk.ArrowType.RIGHT:
            arrow = Gtk.Image.new_from_icon_name('stock_right',
                                                 Gtk.IconSize.BUTTON)

        #~ arrow = Gtk.Arrow.new(arrow_type, Gtk.ShadowType.OUT)
        #~ arrow.set_margin_top(2)
        #~ arrow.set_margin_bottom(2)
        arrow.set_margin_left(2)
        arrow.set_margin_right(2)
        self.add(arrow)

        self.signal_name = signal_name
        self.border_radius = BackForwardButton.BORDER_RADIUS
        return

    def do_draw(self, cr):
        context = self.get_style_context()
        context.save()
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.NORMAL) == 0:
            state = Gtk.StateFlags.PRELIGHT
        context.set_state(state)

        a = self.get_allocation()
        x = 0
        y = 0
        width = a.width
        height = a.height

        if self.arrow_type == Gtk.ArrowType.LEFT:
            width += 10
        elif self.arrow_type == Gtk.ArrowType.RIGHT:
            x -= 10
            width += 10

        Gtk.render_background(context, cr,
                              x, y, width, height)
        Gtk.render_frame(context, cr,
                         x, y, width, height)

        context.restore()

        for child in self: self.propagate_draw(child, cr)
        return

class Left(ButtonPart):

    def __init__(self, sig_name, arrow_type=Gtk.ArrowType.LEFT):
        ButtonPart.__init__(self, arrow_type, sig_name)
        return


class Right(ButtonPart):

    def __init__(self, sig_name, arrow_type=Gtk.ArrowType.RIGHT):
        ButtonPart.__init__(self, arrow_type, sig_name)
        return


# this is used in the automatic tests as well
def get_test_backforward_window():
    win = Gtk.Window()
    win.set_border_width(20)
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.set_default_size(300,100)
    backforward = BackForwardButton()
    win.add(backforward)
    return win

if __name__ == "__main__":
    win = get_test_backforward_window()
    win.show_all()

    Gtk.main()
