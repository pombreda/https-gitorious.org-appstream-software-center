# Copyright (C) 2010 Canonical
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

from softwarecenter.view.appview import AppViewFilter

class SoftwareChannel(object):
    """
    class to represent a software channel
    """
    
    def __init__(self, channel_name, channel_origin, channel_component, requires_filter=False):
        """
        configure the software channel object based on channel name,
        origin, and component (the latter for detecting the partner
        channel)
        """
        self.require_filter = require_filter
        self._channel_name = channel_name
        self._channel_origin = channel_origin
        self._channel_component = channel_component
        self._channel_display_name = self._get_display_name_for_channel(channel_name, channel_component)
        self._channel_icon = self._get_icon_for_channel(channel_name, channel_origin, channel_component)
        self._channel_query = self._get_channel_query_for_channel(channel_name, channel_component)
        self._apps_filter = self._get_apps_filter_for_channel(channel_name)
        
    def get_channel_name(self):
        """
        return the channel name as represented in the xapian database
        """
        return self._channel_name
        
    def get_channel_origin(self):
        """
        return the channel origin as represented in the xapian database
        """
        return self._channel_origin
        
    def get_channel_component(self):
        """
        return the channel component as represented in the xapian database
        """
        return self._channel_component
       
    def get_channel_display_name(self):
        """
        return the display name for the corresponding channel for use in the UI
        """
        return self._channel_display_name
        
    def get_channel_icon(self):
        """
        return the icon that corresponds to each channel based
        on the channel name, its origin string or its component
        """
        return self._channel_icon

    def get_channel_query(self):
        """
        return the xapian query to be used with this software channel
        """
        return self._channel_query
        
    def get_apps_filter(self):
        """
        return the AppView filter to be used with this channel, or
        None if one is not needed
        """
        return self._apps_filter
        
    # TODO:  implement __cmp__ so that sort for channels is encapsulated
    #        here as well
    
    def _get_display_name_for_channel(self, channel_name, channel_component):
        if channel_component == "partner":
            channel_display_name = _("Canonical Partners")
        if not channel_name:
            channel_display_name = _("Other")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_display_name = self.distro.get_distro_channel_description()
        else:
            channel_display_name = channel_name
        return channel_display_name
    
    def _get_icon_for_channel(self, channel_name, channel_origin, channel_component):
        if channel_component == "partner":
            channel_icon = self._get_icon("partner")
        elif not channel_name:
            channel_icon = self._get_icon("unknown-channel")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_icon = self._get_icon("distributor-logo")
        elif channel_origin and channel_origin.startswith("LP-PPA"):
            channel_icon = self._get_icon("ppa")
        # TODO: add check for generic repository source (e.g., Google, Inc.)
        #       self._get_icon("generic-repository")
        else:
            channel_icon = self._get_icon("unknown-channel")
        return channel_icon
    
    def _get_channel_query_for_channel(self, channel_name, channel_component):
    
        if channel_component == "partner":
            channel_query = xapian.Query("XOCpartner")
#        elif channel_name == self.distro.get_distro_channel_name():
#            channel_query = 
        else:
            channel_query = xapian.Query("XOL" + channel_name)
        return channel_query
    
    def _get_apps_filter_for_channel(self, channel_name):
        # the distro channel needs a filter
        if channel_name == self.distro.get_distro_channel_name():
            apps_filter = AppViewFilter(db, cache)
            apps_filter.set_only_packages_without_applications(True)
        else:
            apps_filter = None
        return apps_filter

    def _get_icon(self, icon_name):
        if self.icons.lookup_icon(icon_name, self.ICON_SIZE, 0):
            icon = AnimatedImage(self.icons.load_icon(icon_name, self.ICON_SIZE, 0))
        else:
            # icon not present in theme, probably because running uninstalled
            icon = AnimatedImage(self.icons.load_icon("gtk-missing-image", 
                                                      self.ICON_SIZE, 0))
        return icon
        
        

