# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche
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

from gi.repository import Gtk

class MenuButton(Gtk.Button):

    def __init__(self, menu, icon=None, label=None):
        super(MenuButton, self).__init__()

        self.connect("button-press-event", self.on_button_pressed, menu)
        self.connect("clicked", self.on_keyboard_clicked, menu)
        if icon:
            self.set_image(icon)
        if label:
            self.set_label(label)
        #self.connect("draw", self.on_draw)        

    def on_button_pressed(self, button, event, menu):
        menu.popup(None, None, self.menu_positionner, (button, event.x), event.button, event.time)

    def on_keyboard_clicked(self, button, menu):
        menu.popup(None, None, self.menu_positionner, (button, None), 1, Gtk.get_current_event_time())

    def menu_positionner(self, menu, (button, x_cursor_pos)):
        (button_id, x, y) = button.get_window().get_origin()

        # compute button position
        x_position = x + button.get_allocation().x
        y_position = y + button.get_allocation().y + button.get_allocated_height()
        
        # if pressed by the mouse, show it at the X position of it
        if x_cursor_pos:
            x_position += int(x_cursor_pos)

        # computer current monitor height
        current_screen = button.get_screen()
        num_monitor = current_screen.get_monitor_at_point(x_position, y_position)
        monitor_height = current_screen.get_monitor_geometry(num_monitor).height
        
        # if the menu is too long for the monitor, put it above the widget
        if monitor_height < y_position + menu.get_allocated_height():
            y_position = y_position - button.get_allocated_height() - menu.get_allocated_height()
            
        return (x_position, y_position, True)

    # TODO:
    # would be nice to draw an arrow, but for that, we should connect to get_preferred_width
    # to add the necessary space (what signal? there is none in gtkwidget)
    # and see why it draws behing the button.
    def on_draw(self, widget, cr):
        state = widget.get_state_flags()
        context = widget.get_style_context()
        context.save()
        context.set_state(state)
        Gtk.render_arrow (context, cr, 90,
                          10, 3,
                          150)
        context.restore()


if __name__ == "__main__":

    win = Gtk.Window()
    win.set_size_request(200, 300)

    menu = Gtk.Menu()
    menuitem = Gtk.MenuItem(label="foo")
    menuitem2 = Gtk.MenuItem(label="bar")
    menu.append(menuitem)
    menu.append(menuitem2)
    menuitem.show()
    menuitem2.show()

    box1 = Gtk.Box()
    box1.pack_start(Gtk.Label("something before to show we don't cheat"), True, True, 0)
    win.add(box1)

    box2 = Gtk.Box()
    box2.set_orientation(Gtk.Orientation.VERTICAL)    
    box1.pack_start(box2, True, True, 0)
    box2.pack_start(Gtk.Label("first label with multiple line"), True, True, 0)
 
    image = Gtk.Image.new_from_stock(Gtk.STOCK_PROPERTIES, Gtk.IconSize.BUTTON)
    label = "fooo"
    button_with_menu = MenuButton(menu, image, label)
    box2.pack_start(button_with_menu, False, False, 1)   

    win.connect("destroy", lambda x: Gtk.main_quit())
    win.show_all()

    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-button-images", True)
        
    Gtk.main()
