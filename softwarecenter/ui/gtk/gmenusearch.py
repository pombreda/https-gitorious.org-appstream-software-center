# Copyright (C) 2011 Canonical
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

import os
from softwarecenter.enums import APP_INSTALL_PATH_DELIMITER

import gmenu

class GMenuSearcher(object):

    def __init__(self):
        self._found = None
    def _search_gmenu_dir(self, dirlist, needle):
        if not dirlist[-1]:
            return
        for item in dirlist[-1].get_contents():
            mtype = item.get_type()
            if mtype == gmenu.TYPE_DIRECTORY:
                self._search_gmenu_dir(dirlist+[item], needle)
            elif item.get_type() == gmenu.TYPE_ENTRY:
                desktop_file_path = item.get_desktop_file_path()
                # direct match of the desktop file name and the installed
                # desktop file name
                if os.path.basename(desktop_file_path) == needle:
                    self._found = dirlist+[item]
                    return
                # if there is no direct match, take the part of the path after 
                # "applications" (e.g. kde4/amarok.desktop) and
                # change "/" to "__" and do the match again - this is what
                # the data extractor is doing
                if "applications/" in desktop_file_path:
                    path_after_applications = desktop_file_path.split("applications/")[1]
                    if needle == path_after_applications.replace("/", APP_INSTALL_PATH_DELIMITER):
                        self._found = dirlist+[item]
                        return

                
    def get_main_menu_path(self, desktop_file, menu_files_list=None):
        if not desktop_file:
            return None
        # use the system ones by default, but allow override for
        # easier testing
        if menu_files_list is None:
            menu_files_list = ["applications.menu", "settings.menu"]
        for n in menu_files_list:
            tree = gmenu.lookup_tree(n)
            self._search_gmenu_dir([tree.get_root_directory()], 
                                   os.path.basename(desktop_file))
            if self._found:
                return self._found
        return None
