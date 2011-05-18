# Copyright (C) 2010 Canonical
#
# Authors:
#   Matthew McGowan
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


from mkit import HLinkButton, EM


class ActionBar(gtk.Alignment):

    """ A reimplementation of the original ActionBar.  This version is designed to be
        visually more consistent with the rest of s-c.

        NOTE: Has an altered api and currently lacks a lot of functionality.
    """

    def __init__(self):
        gtk.Alignment.__init__(self, xscale=1.0)
        self.set_padding(0, 0, EM, EM)

        self.hbox = gtk.HBox()
        self.add(self.hbox)

        self._hide = HLinkButton(_('Hide'))
        self._hide.set_underline(True)
        self._hide.set_xmargin(0)

        self._link = HLinkButton('None')
        self._link.set_underline(True)
        self._link.set_xmargin(0)

        self._accompanying_text = gtk.Label('...')
        self._callback = None

        self.hbox.pack_end(self._hide, False)

        self.hbox.pack_start(self._link, False)
        self.hbox.pack_start(self._accompanying_text, False)

        self._hide.connect('clicked', self._on_hide_clicked)
        self._link.connect('clicked', self._on_link_clicked)
        self.show_all()

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, widget, event):
        """ Draw a horizontal line that separates the widget from the page content """

        a = widget.allocation
        self.style.paint_shadow(widget.window, self.state,
                                gtk.SHADOW_IN,
                                (a.x, a.y-6, a.width, 1),
                                widget, "viewport",
                                a.x, a.y-6,
                                a.width, a.y-6)
        return

    def _on_hide_clicked(self, link):
        """ hide the action bar """
        self.hide()
        return

    def _on_link_clicked(self, link):
        """ execute the link onclick callback """

        if self._callback:
            self._callback()
        return

    def set_accompanying_text(self, text, insert_space=True):
        """ sets the text that elaborates on the link label """

        if insert_space:
            text = ' %s' % text
        self._accompanying_text.set_markup(text)
        return

    def set_callback(self, cb):
        """ set the callback for when the link's "clicked" signal is emitted """

        self._callback = cb
        return

    def set_link_label(self, label):
        """ set the link label """

        self._link.set_label(label)
        return

    def add_button(self, *args, **kwargs):
        raise NotImplementedError

    def remove_button(self, *args, **kwargs):
        raise NotImplementedError

    def set_label(self, *args, **kwargs):
        raise NotImplementedError

    def unset_label(self, *args, **kwargs):
        raise NotImplementedError

    def clear(self, *args, **kwargs):
        raise NotImplementedError

    def add_with_properties(self, *args, **kwargs):
        raise NotImplementedError

