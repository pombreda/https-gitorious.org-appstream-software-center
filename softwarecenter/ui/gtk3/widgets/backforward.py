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
from gi.repository import GObject

from gettext import gettext as _

DEFAULT_PART_SIZE = (28, -1)


class BackForwardButton(Gtk.HBox):

    __gsignals__ = {'left-clicked':(GObject.SignalFlags.RUN_LAST,
                                    None,
                                    ()),

                    'right-clicked':(GObject.SignalFlags.RUN_LAST,
                                    None,
                                    ())}

    def __init__(self, part_size=None):
        Gtk.HBox.__init__(self)
        #~ self.set_spacing(1)

        part_size = part_size or DEFAULT_PART_SIZE

        if self.get_direction() != Gtk.TextDirection.RTL:
            # ltr
            self.left = Left('left-clicked', part_size)
            self.right = Right('right-clicked', part_size)
            self.set_button_atk_info_ltr()
        else:
            # rtl
            self.left = Right('left-clicked', part_size, Gtk.ArrowType.LEFT)
            self.right = Left('right-clicked', part_size, Gtk.ArrowType.RIGHT)
            self.set_button_atk_info_rtl()

        atk_obj = self.get_accessible()
        atk_obj.set_name(_('History Navigation'))
        atk_obj.set_description(_('Navigate forwards and backwards.'))
        atk_obj.set_role(Atk.Role.PANEL)

        self.pack_start(self.left, True, True, 0)
        self.pack_end(self.right, True, True, 0)

        #~ self.connect("draw", self.on_draw)
        self.left.connect("clicked", self.on_clicked)
        self.right.connect("clicked", self.on_clicked)
        return

    def on_clicked(self, button):
        self.emit(button.signal_name)
        return

    def on_draw(self, widget, cr):
        #~ a = self.get_allocation()
#~ 
        #~ context = self.get_style_context()
        #~ context.set_state(self.get_state_flags())
        #~ context.save()
        #~ context.add_class("button")
#~ 
        #~ # paint the separator vertical line
        #~ cr.move_to(a.width*0.5, 1)
        #~ cr.rel_line_to(0, a.height-2)
        #~ rgba = context.get_border_color(Gtk.StateFlags.NORMAL)
        #~ cr.set_source_rgb(rgba.red, rgba.green, rgba.blue)
        #~ cr.set_line_width(1)
        #~ cr.stroke()
#~ 
        #~ context.restore()
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

    def __init__(self, arrow_type, signal_name, part_size):
        Gtk.Button.__init__(self)
        #~ self.set_visible_window(False)
        self.set_size_request(*part_size)
        self.set_relief(Gtk.ReliefStyle.NONE)

        alignment = Gtk.Alignment.new(0.5,0.5,1.0,1.0)
        alignment.set_padding(5,5,5,5)
        self.add(alignment)

        arrow = Gtk.Arrow.new(arrow_type, Gtk.ShadowType.OUT)
        alignment.add(arrow)

        self.signal_name = signal_name
        return


class Left(ButtonPart):

    def __init__(self, sig_name, part_size, arrow_type=Gtk.ArrowType.LEFT):
        ButtonPart.__init__(self,
                            arrow_type,
                            sig_name,
                            part_size)

        self.set_name("left-bf-button")

        #~ state = Gtk.StateFlags.NORMAL
        #~ context = self.get_style_context()
#~ 
        #~ border = context.get_property("border-radius", state)
        #~ provider = Gtk.CssProvider()
#~ 
        #~ provider.load_from_file(Gio.file_new_for_path("softwarecenter/ui/gtk3/panes/views/widgets/css/backforward.css"))
        #~ Gtk.StyleContext.add_provider(context, provider, 800)
        #~ context.get_style_property("border-radius", Gtk.StateFlags.NORMAL)
        return


class Right(ButtonPart):

    def __init__(self, sig_name, part_size, arrow_type=Gtk.ArrowType.RIGHT):
        ButtonPart.__init__(self,
                            arrow_type,
                            sig_name,
                            part_size)

        self.set_name("right-bf-button")

        #~ state = Gtk.StateFlags.NORMAL
        #~ context = self.get_style_context()
#~ 
        #~ border = context.get_property("border-radius", state)
        #~ provider = Gtk.CssProvider()
#~ 
        #~ provider.load_from_file(Gio.file_new_for_path("softwarecenter/ui/gtk3/panes/views/widgets/css/backforward.css"))
        #~ Gtk.StyleContext.add_provider(context, provider, 800)
        #~ context.get_style_property("border-radius", Gtk.StateFlags.NORMAL)
        return


if __name__ == "__main__":
    win = Gtk.Window()
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.set_default_size(300,100)
    backforward = BackForwardButton()
    win.add(backforward)
    win.show_all()

    Gtk.main()