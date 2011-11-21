# Copyright (C) 2011 Canonical
#
# Authors:
#  Gary Lasker
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

class UnityLauncherInfo(object):
    """ Simple class to keep track of application details needed for
        Unity launcher integration
    """
    def __init__(self,
                 name,
                 icon_name,
                 icon_file_path,
                 icon_x,
                 icon_y,
                 icon_size,
                 app_install_desktop_file_path,
                 installed_desktop_file_path,
                 trans_id):
        self.name = name
        self.icon_name = icon_name
        self.icon_file_path = icon_file_path
        self.icon_x = icon_x
        self.icon_y = icon_y
        self.icon_size = icon_size
        self.app_install_desktop_file_path = app_install_desktop_file_path
        self.installed_desktop_file_path = installed_desktop_file_path
        self.trans_id = trans_id
        self.add_to_launcher_requested = False
        
class UnityLauncher(object):
    """ Implements the integration between Software Center and the Unity
        launcher
    """
    def __init__(self):
        # keep track of applications that are candidates to be added
        # to the Unity launcher
        self.items = {}
