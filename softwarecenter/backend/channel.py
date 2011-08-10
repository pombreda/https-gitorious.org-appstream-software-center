# Copyright (C) 2010 Canonical
#
# Authors:
#  Gary Lasker
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

import logging
import xapian

from gettext import gettext as _

from softwarecenter.distro import get_distro

from softwarecenter.enums import (SortMethods, 
                                  Icons,
                                 )

LOG = logging.getLogger(__name__)

class ChannelsManager(object):
    @property
    def channels(self):
        return []
        
    @property
    def channels_installed_only(self):
        return []

    @staticmethod
    def channel_available(channelname):
        pass

class SoftwareChannel(object):
    """
    class to represent a software channel
    """
    
    ICON_SIZE = 24
    
    def __init__(self, channel_name, channel_origin, channel_component,
                 source_entry=None, installed_only=False,
                 channel_icon=None, channel_query=None,
                 channel_sort_mode=SortMethods.BY_ALPHABET):
        """
        configure the software channel object based on channel name,
        origin, and component (the latter for detecting the partner
        channel)
        """
        self._channel_name = channel_name
        self._channel_origin = channel_origin
        self._channel_component = channel_component
        self._channel_color = None
        self._channel_view_id = None
        self.installed_only = installed_only
        self._channel_sort_mode = channel_sort_mode
        # distro specific stuff
        self.distro = get_distro()
        # configure the channel
        self._channel_display_name = self._get_display_name_for_channel(channel_name, channel_component)
        if channel_icon is None:
            self._channel_icon = self._get_icon_for_channel(channel_name, channel_origin, channel_component)
        else:
            self._channel_icon = channel_icon
        if channel_query is None:
            self._channel_query = self._get_channel_query_for_channel(channel_name, channel_origin, channel_component)
        else:
            self._channel_query = channel_query
        # a sources.list entry attached to the channel (this is currently
        # only used for not-yet-enabled channels)
        self._source_entry = source_entry
        # when the channel needs to be added to the systems sources.list
        self.needs_adding = False
        
    @property
    def name(self):
        """
        return the channel name as represented in the xapian database
        """
        return self._channel_name
       
    @property 
    def origin(self):
        """
        return the channel origin as represented in the xapian database
        """
        return self._channel_origin
    
    @property    
    def component(self):
        """
        return the channel component as represented in the xapian database
        """
        return self._channel_component
    
    @property   
    def display_name(self):
        """
        return the display name for the corresponding channel for use in the UI
        """
        return self._channel_display_name
    
    @property    
    def icon(self):
        """
        return the icon that corresponds to each channel based
        on the channel name, its origin string or its component
        """
        return self._channel_icon

    @property
    def query(self):
        """
        return the xapian query to be used with this software channel
        """
        return self._channel_query
    
    @property    
    def sort_mode(self):
        """
        return the sort mode for this software channel
        """
        return self._channel_sort_mode
        
    # TODO:  implement __cmp__ so that sort for channels is encapsulated
    #        here as well

    def _get_display_name_for_channel(self, channel_name, channel_component):
        if channel_component == "partner":
            channel_display_name = _("Canonical Partners")
        elif not channel_name:
            channel_display_name = _("Unknown")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_display_name = self.distro.get_distro_channel_description()
        elif channel_name == "For Purchase":
            channel_display_name = _("For Purchase")
        elif channel_name == "Application Review Board PPA":
            channel_display_name = _("Independent")
        elif channel_name == "notdownloadable":
            channel_display_name = _("Other")
        else:
            return channel_name
        return channel_display_name
    
    def _get_icon_for_channel(self, channel_name, channel_origin, channel_component):
        if channel_component == "partner":
            channel_icon = "partner"
        elif not channel_name:
            channel_icon = "unknown-channel"
        elif channel_name == self.distro.get_distro_channel_name():
            channel_icon = "distributor-logo"
        elif channel_name == "Application Review Board PPA":
            channel_icon = "system-users"
        elif channel_name == "For Purchase":
            channel_icon = "emblem-money"
        elif channel_origin and channel_origin.startswith("LP-PPA"):
            channel_icon = "ppa"
        elif channel_name == "notdownloadable":
            channel_icon = "application-default-icon"
        # TODO: add check for generic repository source (e.g., Google, Inc.)
        #       channel_icon = "generic-repository"
        else:
            channel_icon = "unknown-channel"
        return channel_icon
    
    def _get_channel_query_for_channel(self, channel_name, channel_origin, channel_component):
    
        if channel_component == "partner":
            q1 = xapian.Query("XOCpartner")
            q2 = xapian.Query("AH%s-partner" % self.distro.get_codename())
            channel_query = xapian.Query(xapian.Query.OP_OR, q1, q2)
        # show only apps when displaying the new apps archive
        elif channel_name == "Application Review Board PPA":
            channel_query = xapian.Query(xapian.Query.OP_AND, 
                                         xapian.Query("XOL" + channel_name),
                                         xapian.Query("ATapplication"))
        elif channel_origin:
            channel_query = xapian.Query("XOO" + channel_origin)
        else:
            channel_query = xapian.Query("XOL" + channel_name)
        return channel_query

    def __str__(self):
        details = []
        details.append("* SoftwareChannel")
        details.append("  name: %s" % self.name)
        details.append("  origin: %s" % self.origin)
        details.append("  component: %s" % self.component)
        details.append("  display_name: %s" % self.display_name)
        details.append("  iconname: %s" % self.icon)
        details.append("  query: %s" % self.query)
        details.append("  sort_mode: %s" % self.sort_mode)
        details.append("  installed_only: %s" % self.installed_only)
        return '\n'.join(details)


class AllChannel(SoftwareChannel):

    def __init__(self, channel_name, installed_only):
        SoftwareChannel.__init__(
            self, channel_name, "all", None,
            installed_only=installed_only,
            channel_icon=Icons.FALLBACK)
        return

    # overrides
    def _get_display_name_for_channel(self, channel_name, _):
        return channel_name

    def _get_channel_query_for_channel(self, *args):
        return None


class AllAvailableChannel(AllChannel):

    def __init__(self):
        AllChannel.__init__(self, _("All Software"), False)


class AllInstalledChannel(AllChannel):

    def __init__(self):
        AllChannel.__init__(self, _("All Installed"), True)

# singleton
channels_manager = None
def get_channels_manager(db):
    global channels_manager
    if channels_manager is None:
        from softwarecenter.backend.aptchannels import AptChannelsManager
        channels_manager = AptChannelsManager(db)
    return channels_manager

def is_channel_available(channelname):
    from softwarecenter.backend.aptchannels import AptChannelsManager
    return AptChannelsManager.channel_available(channelname)

if __name__ == "__main__":
    distro = get_distro()
    channel = SoftwareChannel(distro.get_distro_channel_name(), 
                              None, None)
    print(channel)
    channel = SoftwareChannel(distro.get_distro_channel_name(), None, "partner")
    print(channel)

