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
import logging

from gettext import gettext as _
from mkit import HLinkButton, EM

LOG = logging.getLogger(__name__)

class ActionBar(gtk.HBox):
    """
    This is a gtk box wrapped so that all child widgets, save one, align
    to the right. The widget does not show by default when its parent
    calls show_all(), but rather autoshows and autohides when buttons
    (or a left-aligned label) are added and removed. 

    The widget is only intended to hold buttons and a label, for which
    it has specific methods; general add and pack are not implemented.

    See: https://wiki.ubuntu.com/SoftwareCenter#Main%20window
    https://wiki.ubuntu.com/SoftwareCenter#Custom%20package%20lists
    https://wiki.ubuntu.com/SoftwareCenter#software-list-view-disclosure
    """

    def __init__(self):
        super(ActionBar, self).__init__()
        self._btns = gtk.HBox()
        self._label = gtk.HBox()
        # So that all buttons children right align
        self._btn_bin = gtk.Alignment(xalign=1)
        self._btn_bin.add(self._btns)
        # Buttons go on the right, labels on the left (in LTR mode)
        super(ActionBar, self).pack_start(self._label, fill=False,
                                          expand=False, padding=10)
        super(ActionBar, self).pack_start(self._btn_bin)

        # Don't show_all() by default.
        self.set_no_show_all(True)
        self._label.show_all()
        self._btn_bin.show_all()
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
            self._btns.remove(overwrite)
        btn = HLinkButton(label)
        btn.set_underline(True)
        btn.connect("clicked", self._callback(result, result_args))
        btn.id = id
        btn.show()
        self._btns.pack_start(btn)

        if not self._visible:
            self._show()

    def remove_button(self, id):
        """Removes a button. Hides bar if no buttons left."""
        children = self._btns.get_children()
        for child in children:
            if child.id == id:
                self._btns.remove(child)
                if len(children) == 1 and not len(self._label):
                    self._hide()
                return

    def set_label(self, text, link_result=None, *link_result_args):
        """
        Places a string on the right and shows the actionbar.
        Note the "_" symbol acts to delimit sections treated as a link.
        For example, in text="Lorem _ ipsum_ dolor _sit amat", clicking
        the section " ipsum" or "sit amat" will trigger the link_result.

        Keyword arguments:
        text -- a string optionally with "_" to indicate a link button.
        link_result -- A function to be called on link click
        link_result_args -- Any arguments for the result function
        """

        sections = text.split("_")
        LOG.debug("got sections '%s'" % sections)

        # Unfortunately, gtk has no native method for embedding a link
        # in a gtk.Label with non-link elements. To represent the label,
        # this method makes an eventbox for each link and non-link
        # section. If the section corresponds to a link, it hooks hover,
        # unhover, and click behavior to the box.
        while len(self._label) > len(sections):
            last = self._label.get_children()[-1]
            self._label.remove(last)
        while len(self._label) < len(sections):
            box = gtk.EventBox()
            self._label.pack_start(box)
            # Sections alternate between link and non-link types, so
            # hook up link methods to even sections.
            if not len(self._label) % 2:
                box.connect("button-press-event",
                            self._callback(link_result, link_result_args))
                box.connect("enter-notify-event", self._hover_link)
                box.connect("leave-notify-event", self._unhover_link)

        # Finally, place the text segments in their respective event
        # boxes. Use pango to underline link segments.
        for i, box in enumerate(self._label):
            label = gtk.Label()
            markup = sections[i]
            if i % 2:
                markup = "<u>%s</u>" % markup
            label.set_markup(markup)
            if box.get_child():
                box.remove(box.get_child())
            box.add(label)
            box.show_all()
        self._show()

    def unset_label(self):
        """
        Removes the currently set label, hiding the actionbar if no
        buttons are displayed.
        """
        # Destroy all event boxes holding text segments.
        while len(self._label):
            last = self._label.get_children()[-1]
            self._label.remove(last)
        if self.window:
            self.window.set_cursor(None)
        # Then hide if there's nothing else visible.
        if not len(self._btns):
            self._hide()

    def get_button(self, id):
        """Returns a button, or None if `id` links to no button."""
        for child in self._btns.get_children():
            if child.id == id:
                return child

    def clear(self):
        """Removes all contents and hides the bar."""
        for child in self._btns.get_children():
            self._btns.remove(child)
        self.unset_label()
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

    def pack_start(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_default_start(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_end(self, *args):
        """Not Implemented: Do not call."""
        raise NotImplementedError

    def pack_default_end(self, *args):
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
        callback = lambda *trash_args: function(*args)
        return callback

    def _hover_link(self, linkbox, *args):
        # Makes the link in given eventbox bold
        label = linkbox.get_child()
        label.set_markup("<b><u>%s</u></b>" % label.get_text())
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))

    def _unhover_link(self, linkbox, *args):
        # Sets the link in given eventbox to its base state
        label = linkbox.get_child()
        label.set_markup("<u>%s</u>" % label.get_text())
        self.window.set_cursor(None)


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

    def perform_lbl():
        print "Clicked label link"

    def add_func(*args):
        global btns
        btns += 1
        bar.add_button(btns, "Perform %i action" % btns, perform, btns)

    def rmv_func(*args):
        global btns
        if btns > 0:
            bar.remove_button(btns)
            btns -= 1

    def set_func(*args):
        bar.set_label("This label _has a link", perform_lbl)

    def unset_func(*args):
        bar.unset_label()

    addbtn = gtk.Button("Add Button")
    rmvbtn = gtk.Button("Remove Button")
    setbtn = gtk.Button("Set Label")
    unsetbtn = gtk.Button("Unset Label")
    addbtn.connect("clicked", add_func)
    rmvbtn.connect("clicked", rmv_func)
    setbtn.connect("clicked", set_func)
    unsetbtn.connect("clicked", unset_func)
    control_box.pack_start(addbtn)
    control_box.pack_start(rmvbtn)
    control_box.pack_start(setbtn)
    control_box.pack_start(unsetbtn)

    win.add(box)
    box.pack_start(control_box, expand=False)
    box.pack_start(tree)
    box.pack_start(bar, expand=False, padding=5)
    win.connect("destroy", gtk.main_quit)
    win.show_all()

    gtk.main()
