#!/usr/bin/python
# -*- coding: utf-8 -*-

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

import gtk
import gobject
import logging
import os
        
import softwarecenter.paths
from softwarecenter.paths import SOFTWARE_CENTER_AGENT_HELPER
from spawn_helper import SpawnHelper
from softwarecenter.utils import get_language
from softwarecenter.distro import get_distro, get_current_arch

LOG = logging.getLogger(__name__)

class SoftwareCenterAgent(gobject.GObject):

    __gsignals__ = {
        "available-for-me" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT,),
                             ),
        "available" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT,),
                             ),
        "error" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, 
                   (str,),
                  ),
        }
    
    def __init__(self, ignore_cache=False):
        gobject.GObject.__init__(self)
        self.distro = get_distro()
        self.ignore_cache = ignore_cache
        self.HELPER_BINARY = os.path.join(
            softwarecenter.paths.datadir, SOFTWARE_CENTER_AGENT_HELPER)

    def query_available(self, series_name=None, arch_tag=None):
        self._query_available(series_name, arch_tag, for_qa=False)

    def query_available_qa(self, series_name=None, arch_tag=None):
        self._query_available(series_name, arch_tag, for_qa=True)

    def _query_available(self, series_name, arch_tag, for_qa):
        language = get_language()
        if not series_name:
            series_name = self.distro.get_codename()
        if not arch_tag:
            arch_tag = get_current_arch()
        # build the command
        cmd = [self.HELPER_BINARY]
        if self.ignore_cache:
            cmd.append("--ignore-cache")
        if for_qa:
            cmd.append("available_apps_qa")
        else:
            cmd.append("available_apps")
        cmd += [language,
                series_name,
                arch_tag,
                ]
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_query_available_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_query_available_data(self, spawner, piston_available):
        self.emit("available", piston_available)

    def query_available_for_me(self, oauth_token, openid_identifier):
        cmd = [self.HELPER_BINARY,
               "subscriptions_for_me"]
        if self.ignore_cache:
            cmd.append("--ignore-cache")
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_query_available_for_me_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_query_available_for_me_data(self, spawner, piston_available_for_me):
        self.emit("available-for-me", piston_available_for_me)

if __name__ == "__main__":
    def _available(agent, available):
        print "_available: ", available
    def _available_for_me(agent, available_for_me):
        print "_availalbe_for_me: ", available_for_me

    # test specific stuff
    logging.basicConfig()
    softwarecenter.paths.datadir = "./data"

    scagent = SoftwareCenterAgent()
    scagent.connect("available-for-me", _available_for_me)
    scagent.connect("available", _available)
    scagent.query_available("natty", "i386")
    scagent.query_available_for_me("dummy_oauth", "dummy openid")

    gtk.main()
