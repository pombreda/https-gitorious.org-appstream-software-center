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

class HardwareRequirementsLabel(Gtk.HBox):
    """ contains a single HW requirement string and a image that shows if 
        the requirements are meet 
    """
    def get_label(self):
        return ""
    def get_icon_name(self):
        return ""
    def set_hardware_requirement(self, tag, result):
        pass

class HardwareRequirementsBox(Gtk.HBox):
    """ A collection of HW requirement labels """

    def set_hardware_requirements(self, hw_requirements_result):
        pass

    @property
    def hw_labels(self):
        return []
