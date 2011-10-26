# -*- coding: utf-8 -*-
# Copyright (C) 2011 Canonical
#
# Authors:
#  Didier Roche
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

from gi.repository import GObject


class OneConfHandler(GObject.GObject):

    """A fake oneconf handler."""

    __gsignals__ = {
        "show-oneconf-changed" : (GObject.SIGNAL_RUN_LAST,
                                  GObject.TYPE_NONE,
                                  (GObject.TYPE_PYOBJECT,),
                                 ),
        "last-time-sync-changed" : (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE,
                                    (GObject.TYPE_PYOBJECT,),
                                   ),
        }

    def __init__(self, oneconfviewpickler):
        '''Controller of the installed pane'''
        super(OneConfHandler, self).__init__()

        self.already_registered_hostids = []
        self.is_current_registered = True

        self.oneconfviewpickler = oneconfviewpickler

    def refresh_hosts(self):
        """refresh hosts list in the panel view"""
        pass

    def get_latest_oneconf_sync(self):
        '''Get latest sync state in OneConf.

        This function is also the "ping" letting OneConf service alive'''
        return True

    def sync_between_computers(self, sync_on):
        '''toggle the sync on and off if needed between computers'''
        pass

