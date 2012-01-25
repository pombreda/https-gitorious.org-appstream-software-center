# Copyright (C) 2012 Canonical
#
# Authors:
#  Michael Vogt
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
from gettext import gettext as _

TAG_DESCRIPTION = {
    'hardware::gps' : _('GPS'),
    'hardware::video:opengl' : _('OpenGL hardware acceleration'),
    # FIXME: fill in more
}

TAG_MISSING_DESCRIPTION = {
    'hardware::gps' : _('This software requires a GPS, '
                        'but the computer does not have one.'),
    'hardware::video:opengl' : _('This computer does not have graphics fast '
                                 'enough for this software.'),
    # FIXME: fill in more
}

class HardwareRequirementsLabel(Gtk.HBox):
    """ contains a single HW requirement string and a image that shows if 
        the requirements are meet 
    """

    ICON_SUPPORTED = Gtk.STOCK_APPLY
    ICON_MISSING = Gtk.STOCK_CANCEL

    def __init__(self):
        super(HardwareRequirementsLabel, self).__init__()
        self.tag = None
        self.result = None
        self._build_ui()
    def _build_ui(self):
        self._img = Gtk.Image()
        self._label = Gtk.Label()
        self.pack_start(self._img, True, True, 1)
        self.pack_start(self._label, True, True, 1)
    def get_label(self):
        return _(TAG_DESCRIPTION[self.tag])
    def get_icon_name(self):
        if self.result == "yes":
            return self.ICON_SUPPORTED
        elif self.result == "no":
            return self.ICON_MISSING
    def set_hardware_requirement(self, tag, result):
        self.tag = tag
        self.result = result
        self._label.set_text(self.get_label())
        self._img.set_from_stock(self.get_icon_name(),  Gtk.IconSize.MENU)

class HardwareRequirementsBox(Gtk.HBox):
    """ A collection of HW requirement labels """

    def __init__(self):
        super(HardwareRequirementsBox, self).__init__()

    def clear(self):
        for w in self.get_children():
            self.remove(w)

    def set_hardware_requirements(self, hw_requirements_result):
        self.clear()
        for tag, supported in hw_requirements_result.iteritems():
            # ignore unknown for now
            if not supported in ("yes", "no"):
                continue
            label = HardwareRequirementsLabel()
            label.set_hardware_requirement(tag, supported)
            label.show()
            self.pack_start(label, True, True, 6)

    @property
    def hw_labels(self):
        return self.get_children()


def get_test_window():
    win = Gtk.Window()
    win.set_size_request(300, 200)

    HW_TEST_RESULT = { 'hardware::gps' : 'yes',
                       'hardware::video:opengl' : 'no',
                       }

    # add it
    hwbox = HardwareRequirementsBox()
    hwbox.set_hardware_requirements(HW_TEST_RESULT)
    win.add(hwbox)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
