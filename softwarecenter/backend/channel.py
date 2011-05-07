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

import apt
import glib
import gettext
import logging
import string
import urlparse
import xapian

from aptsources.sourceslist import SourceEntry, SourcesList

from gettext import gettext as _

from softwarecenter.backend import get_install_backend
from softwarecenter.distro import get_distro
from softwarecenter.view.widgets.animatedimage import AnimatedImage
from softwarecenter.utils import *
from softwarecenter.enums import *

LOG = logging.getLogger(__name__)

class ChannelsManager(object):

    def __init__(self, db, icons):
        self.db = db
        self.icons = icons
        self.distro = get_distro()
        self.backend = get_install_backend()
        self.backend.connect("channels-changed", 
                             self._remove_no_longer_needed_extra_channels)
        # kick off a background check for changes that may have been made
        # in the channels list
        glib.timeout_add(300, self._check_for_channel_updates_timer)
        # extra channels from e.g. external sources
        self.extra_channels = []
        self._logger = LOG

    # external API
    @property
    def channels(self):
        """
        return a list of SoftwareChannel objects in display order
        according to:
            Distribution, Partners, PPAs alphabetically, 
            Other channels alphabetically, Unknown channel last
        """
        return self._get_channels()
        
    @property
    def channels_installed_only(self):
        """
        return a list of SoftwareChannel objects displaying installed
        packages only in display order according to:
            Distribution, Partners, PPAs alphabetically, 
            Other channels alphabetically, Unknown channel last
        """
        return self._get_channels(installed_only=True)

    def feed_in_private_sources_list_entries(self, entries):
        added = False
        for entry in entries:
            added |= self._feed_in_private_sources_list_entry(entry)
        if added:
            self.backend.emit("channels-changed", True)

    def add_channel(self, name, icon, query):
        """
        create a channel with the name, icon and query specified and append
        it to the set of channels
        return the new channel object
        """
        # print name, icon, query
        channel = SoftwareChannel(self.icons, name, None, None, 
                                  channel_icon=icon,
                                  channel_query=query)
        self.extra_channels.append(channel)
        self.backend.emit("channels-changed", True)

        if channel.installed_only:
            channel._channel_color = '#aea79f'
            channel._channel_image_id = VIEW_PAGE_INSTALLED
        else:
            channel._channel_color = '#0769BC'
            channel._channel_image_id = VIEW_PAGE_AVAILABLE
        return channel

    # internal
    def _feed_in_private_sources_list_entry(self, source_entry):
        """
        this feeds in a private sources.list entry that is
        available to the user (like a private PPA) that may or
        may not be active 
        """
        # FIXME: strip out password and use apt/auth.conf
        potential_new_entry = SourceEntry(source_entry)
        # look if we have it
        sources = SourcesList()
        for source in sources.list:
            if source == potential_new_entry:
                return False
        # need to add it as a not yet enabled channel
        name = human_readable_name_from_ppa_uri(potential_new_entry.uri)
        # FIXME: use something better than uri as name
        private_channel = SoftwareChannel(self.icons, name, None, None,
                                          source_entry=source_entry)
        private_channel.needs_adding = True
        if private_channel in self.extra_channels:
            return False
        # add it
        self.extra_channels.append(private_channel)
        return True

    def _remove_no_longer_needed_extra_channels(self, backend, res):
        """ go over the extra channels and remove no longer needed ones"""
        removed = False
        for channel in self.extra_channels:
            if not channel._source_entry:
                continue
            sources = SourcesList()
            for source in sources.list:
                if source == SourceEntry(channel._source_entry):
                    self.extra_channels.remove(channel)
                    removed = True
        if removed:
            self.backend.emit("channels-changed", True)

    def _check_for_channel_updates_timer(self):
        """
        run a background timer to see if the a-x-i data we have is 
        still fresh or if the cache has changed since
        """
        if not self.db._aptcache.ready:
            return True
        # see if we need a a-x-i update
        if self._check_for_channel_updates():
            # this will trigger a "channels-changed" signal from
            # the backend object once a-x-i is finished
            self._logger.debug("running update_xapian_index")
            self.backend.update_xapian_index()
        return False

    def _check_for_channel_updates(self):
        """ 
        check current set of channel origins in a-x-i and
        compare it to the apt cache to see if 
        anything has changed, 
        
        returns True is a update is needed
        """
        # the operation get_origins can take some time (~60s?)
        cache_origins = self.db._aptcache.get_origins()
        db_origins = set()
        for channel in self.channels:
            origin = channel.origin
            if origin:
                db_origins.add(origin)
        # origins
        self._logger.debug("cache_origins: %s" % cache_origins)
        self._logger.debug("db_origins: %s" % db_origins)
        if cache_origins != db_origins:
            return True
        return False
    
    def _get_channels(self, installed_only=False):
        """
        (internal) implements 'channels()' and 'channels_installed_only()' properties
        """
        distro_channel_name = self.distro.get_distro_channel_name()
        
        # gather the set of software channels and order them
        other_channel_list = []
        cached_origins = []
        for channel_iter in self.db.xapiandb.allterms("XOL"):
            if len(channel_iter.term) == 3:
                continue
            channel_name = channel_iter.term[3:]
            channel_origin = ""
            
            # get origin information for this channel
            m = self.db.xapiandb.postlist_begin(channel_iter.term)
            doc = self.db.xapiandb.get_document(m.get_docid())
            for term_iter in doc.termlist():
                if term_iter.term.startswith("XOO") and len(term_iter.term) > 3: 
                    channel_origin = term_iter.term[3:]
                    break
            self._logger.debug("channel_name: %s" % channel_name)
            self._logger.debug("channel_origin: %s" % channel_origin)
            if channel_origin not in cached_origins:
                other_channel_list.append((channel_name, channel_origin))
                cached_origins.append(channel_origin)
        
        dist_channel = None
        partner_channel = None
        for_purchase_channel = None
        new_apps_channel = None
        ppa_channels = []
        other_channels = []
        unknown_channel = []
        local_channel = None

        for (channel_name, channel_origin) in other_channel_list:
            if not channel_name:
                unknown_channel.append(SoftwareChannel(self.icons, 
                                                       channel_name,
                                                       channel_origin,
                                                       None,
                                                       installed_only=installed_only))
            elif channel_name == distro_channel_name:
                dist_channel = (SoftwareChannel(self.icons,
                                                distro_channel_name,
                                                channel_origin,
                                                None,
                                                installed_only=installed_only))
            elif channel_name == "Partner archive":
                partner_channel = SoftwareChannel(self.icons, 
                                                  channel_name,
                                                  channel_origin,
                                                  "partner", 
                                                  installed_only=installed_only)
            elif channel_name == "notdownloadable":
                if installed_only:
                    local_channel = SoftwareChannel(self.icons, 
                                                    channel_name,
                                                    None,
                                                    None,
                                                    installed_only=installed_only)
            elif (channel_origin and
                  channel_origin.startswith("LP-PPA-commercial-ppa-uploaders")):
                # do not display commercial private PPAs, they will all be
                # displayed in the "for-purchase" node anyway
                pass
            elif channel_origin and channel_origin.startswith("LP-PPA"):
                if channel_origin == "LP-PPA-app-review-board":
                    new_apps_channel = SoftwareChannel(self.icons, 
                                                       channel_name,
                                                       channel_origin,
                                                       None,
                                                       installed_only=installed_only)
                else:
                    ppa_channels.append(SoftwareChannel(self.icons, 
                                                        channel_name,
                                                        channel_origin,
                                                        None,
                                                        installed_only=installed_only))
            # TODO: detect generic repository source (e.g., Google, Inc.)
            else:
                other_channels.append(SoftwareChannel(self.icons, 
                                                      channel_name,
                                                      channel_origin,
                                                      None,
                                                      installed_only=installed_only))

        # always display the partner channel, even if its source is not enabled                                                       
        if not partner_channel:
            partner_channel = SoftwareChannel(self.icons, 
                                              "Partner archive",
                                              "Canonical",
                                              "partner", 
                                              installed_only=installed_only)
        
        # create a "magic" channel to display items available for purchase                                              
        for_purchase_query = xapian.Query("AH" + AVAILABLE_FOR_PURCHASE_MAGIC_CHANNEL_NAME)
        for_purchase_channel = SoftwareChannel(self.icons, 
                                               "For Purchase", None, None, 
                                               channel_icon=None,   # FIXME:  need an icon
                                               channel_query=for_purchase_query,
                                               installed_only=installed_only)
        
        # set them in order
        channels = []
        if dist_channel is not None:
            channels.append(dist_channel)
        if partner_channel is not None:
            channels.append(partner_channel)
        channels.append(for_purchase_channel)
        if new_apps_channel is not None:
            channels.append(new_apps_channel)
        channels.extend(ppa_channels)
        channels.extend(other_channels)
        channels.extend(unknown_channel)
        channels.extend(self.extra_channels)
        if local_channel is not None:
            channels.append(local_channel)

        for channel in channels:
            if installed_only:
                channel._channel_color = '#aea79f'
                channel._channel_image_id = VIEW_PAGE_INSTALLED
            else:
                channel._channel_color = '#0769BC'
                channel._channel_image_id = VIEW_PAGE_AVAILABLE
        return channels


class SoftwareChannel(object):
    """
    class to represent a software channel
    """
    
    ICON_SIZE = 24
    
    def __init__(self, icons, channel_name, channel_origin, channel_component,
                 source_entry=None, installed_only=False,
                 channel_icon=None, channel_query=None,
                 channel_sort_mode=SORT_BY_ALPHABET):
        """
        configure the software channel object based on channel name,
        origin, and component (the latter for detecting the partner
        channel)
        """
        self._channel_name = channel_name
        self._channel_origin = channel_origin
        self._channel_component = channel_component
        self._channel_color = None
        self._channel_image_id = None
        self.installed_only = installed_only
        self.icons = icons
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
            channel_icon = self._get_icon("partner")
        elif not channel_name:
            channel_icon = self._get_icon("unknown-channel")
        elif channel_name == self.distro.get_distro_channel_name():
            channel_icon = self._get_icon("distributor-logo")
        elif channel_name == "Application Review Board PPA":
            channel_icon = self._get_icon("system-users")
        elif channel_name == "For Purchase":
            channel_icon = self._get_icon("emblem-money")
        elif channel_origin and channel_origin.startswith("LP-PPA"):
            channel_icon = self._get_icon("ppa")
        elif channel_name == "notdownloadable":
            channel_icon = self._get_icon("application-default-icon")
        # TODO: add check for generic repository source (e.g., Google, Inc.)
        #       self._get_icon("generic-repository")
        else:
            channel_icon = self._get_icon("unknown-channel")
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

    def _get_icon(self, icon_name):
        return AnimatedImage(get_icon_from_theme(self.icons, 
                                                 iconname=icon_name, 
                                                 iconsize=self.ICON_SIZE,
                                                 missingicon=GENERIC_MISSING_IMAGE))
        
    def __str__(self):
        details = []
        details.append("* SoftwareChannel")
        details.append("  name: %s" % self.name)
        details.append("  origin: %s" % self.origin)
        details.append("  component: %s" % self.component)
        details.append("  display_name: %s" % self.display_name)
        details.append("  icon: %s" % self.icon)
        details.append("  query: %s" % self.query)
        details.append("  sort_mode: %s" % self.sort_mode)
        details.append("  installed_only: %s" % self.installed_only)
        return '\n'.join(details)
        
if __name__ == "__main__":
    import gtk
    from softwarecenter.enums import *
    icons = gtk.icon_theme_get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(SOFTWARE_CENTER_ICON_PATH)
    distro = get_distro()
    channel = SoftwareChannel(icons, distro.get_distro_channel_name(), 
                              None, None)
    print channel
    channel = SoftwareChannel(icons, distro.get_distro_channel_name(), None, "partner")
    print channel

