# Copyright (C) 2010 Canonical
#
# Authors:
#  Jacob Johan Edwards
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

import gtk


class ActionBar(gtk.Alignment):
    """
    This is a gtk box wrapped so that all child widgets align to the
    right. The widget does not show by default when its parent calls
    show_all(), but rather autoshows and autohides when buttons are
    added and removed.

    The widget is only intended to hold buttons, for which it has
    specific methods; general add() is not implemented.

    See: https://wiki.ubuntu.com/SoftwareCenter#Main%20window
    """

    def __init__(self):
        # So that all children right align
        super(ActionBar, self).__init__(xalign=1)
        self._elems = gtk.HBox()
        super(ActionBar, self).add(self._elems)

        # Don't show_all() default.
        self.set_no_show_all(True)
        self._elems.show()
        self._visible = False

    def add_button(self, id, label, result, *result_args):
        """Adds a button and shows the bar.

        Keyword arguments:
        id -- A unique identifier for the button
        label -- A string for the button label
        result -- A function to be called on button click
        result_args -- Any arguments for the result function
        """
        overwrite = self.get_button(id)
        if overwrite:
            self._elems.remove(overwrite)
        btn = gtk.Button(label)
        btn.connect("clicked", self._callback(result, result_args))
        btn.id = id
        btn.show()
        self._elems.pack_start(btn)

        if not self._visible:
            self._show()

    def remove_button(self, id):
        """Removes a button. Hides bar if no buttons left."""
        children = self._elems.get_children()
        for child in children:
            if child.id == id:
                self._elems.remove(child)
                if len(children) == 1:
                    self._hide()
                return

    def get_button(self, id):
        """Returns a button, or None if `id` links to no button."""
        for child in self._elems.get_children():
            if child.id == id:
                return child

    def clear(self):
        """Removes all contents and hides the bar."""
        for child in self._elems.get_children():
            self._elems.remove(child)
        self._hide()

    # The following gtk.Container methods are deimplemented to prevent
    # overwriting of the _elems children box, and because the only
    # intended contents of an ActionBar are buttons and perhaps a text
    # label.

    def add(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def add_with_properties(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def remove(self, widget):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    # Internal methods

    def _show(self):
        super(ActionBar, self).show()
        self._visible = True

    def _hide(self):
        super(ActionBar, self).hide()
        self._visible = False

    def _callback(self, function, args):
        # Disposes of the 'widget' argument that
        # gtk.Widget.connect() prepends to calls.
        callback = lambda widget: function(*args)
        return callback


if __name__ == "__main__":
    win = gtk.Window()
    win.set_size_request(600, 400)
    box = gtk.VBox()
    control_box = gtk.HBox()
    tree = gtk.TreeView()
    bar = ActionBar()
    btns = 0

    def perform(btn):
        print "Clicked 'Perform %i'" % btn

    def add_func(*args):
        global btns
        btns += 1
        bar.add_button(btns, "Perform %i action" % btns, perform, btns)

    def rmv_func(*args):
        global btns
        if btns > 0:
            bar.remove_button(btns)
            btns -= 1

    addbtn = gtk.Button("Add Button")
    rmvbtn = gtk.Button("Remove Button")
    addbtn.connect("clicked", add_func)
    rmvbtn.connect("clicked", rmv_func)
    control_box.pack_start(addbtn)
    control_box.pack_start(rmvbtn)

    win.add(box)
    box.pack_start(control_box, expand=False)
    box.pack_start(tree)
    box.pack_start(bar, expand=False, padding=5)
    win.connect("destroy", gtk.main_quit)
    win.show_all()

    gtk.main()
