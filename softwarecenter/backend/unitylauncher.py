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

import dbus
import logging

LOG = logging.getLogger(__name__)

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
        # keep track of applications that are candidates for adding
        # to the Unity launcher
        self.launcher_queue = {}
        
    def add_to_launcher_queue(self, pkgname, launcher_info):
        """ add an application to the set of candidates for adding to the
            Unity launcher
        """
        self.launcher_queue[pkgname] = launcher_info
        
    def remove_from_launcher_queue(self, pkgname):
        """ remove an application from the set of candidates for adding to the
            Unity launcher
        """
        if pkgname in self.launcher_queue:
            return self.launcher_queue.pop(pkgname)
        
    def send_application_to_launcher(self, pkgname, launcher_info):
        LOG.debug("sending dbus signal to Unity launcher for application: ", 
                  launcher_info.name)
        LOG.debug("  launcher_info.icon_file_path: ", 
                     launcher_info.icon_file_path)
        LOG.debug("  launcher_info.installed_desktop_file_path: ",
                     launcher_info.installed_desktop_file_path)
        LOG.debug("  launcher_info.trans_id: ", launcher_info.trans_id)
        # the application is being added to the launcher, so clear it from the
        # list of candidates in the launcher queue
        self.remove_from_launcher_queue(pkgname)
        # add the application by sending a dbus signal to the Unity launcher
        try:
            bus = dbus.SessionBus()
            launcher_obj = bus.get_object('com.canonical.Unity.Launcher',
                                          '/com/canonical/Unity/Launcher')
            launcher_iface = dbus.Interface(launcher_obj,
                                            'com.canonical.Unity.Launcher')
            launcher_iface.AddLauncherItemFromPosition(
                    launcher_info.name,
                    launcher_info.icon_file_path,
                    launcher_info.icon_x,
                    launcher_info.icon_y,
                    launcher_info.icon_size,
                    launcher_info.installed_desktop_file_path,
                    launcher_info.trans_id)
        except Exception as e:
            LOG.warn("could not send dbus signal to the Unity launcher: (%s)",
                     e)
