# Copyright (C) 2009 Canonical
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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from softwarecenter.paths import ICON_PATH

import os

def get_sc_icon_theme(datadir):
    # additional icons come from app-install-data
    icons = Gtk.IconTheme.get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir,"icons"))
    icons.append_search_path(os.path.join(datadir,"emblems"))
    # HACK: make it more friendly for local installs (for mpt)
    icons.append_search_path(datadir+"/icons/32x32/status")
    # add the humanity icon theme to the iconpath, as not all icon 
    # themes contain all the icons we need
    # this *shouldn't* lead to any performance regressions
    path = '/usr/share/icons/Humanity'
    if os.path.exists(path):
        for subpath in os.listdir(path):
            subpath = os.path.join(path, subpath)
            if os.path.isdir(subpath):
                for subsubpath in os.listdir(subpath):
                    subsubpath = os.path.join(subpath, subsubpath)
                    if os.path.isdir(subsubpath):
                        icons.append_search_path(subsubpath)
    return icons

