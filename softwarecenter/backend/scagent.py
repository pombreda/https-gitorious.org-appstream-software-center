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

import glib
import gtk
import gobject
import logging
import os
import cPickle
        
import softwarecenter.paths
from softwarecenter.paths import SOFTWARE_CENTER_AGENT_HELPER
from spawn_helper import SpawnHelper

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

    def __init__(self):
        gobject.GObject.__init__(self)

    def query_available(self, series_name=None, arch_tag=None, for_qa=False):
        # run the command and add watcher
        language= "any"
        binary = os.path.join(
            softwarecenter.paths.datadir, SOFTWARE_CENTER_AGENT_HELPER)
        cmd = [binary,
               "available_apps",
               language,
               series_name,
               arch_tag,
               ]
        spawner = SpawnHelper()
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.connect("data-available", self._on_query_available_ready)
        spawner.spawn_helper(cmd)

    def _on_query_available_ready(self, spawner, piston_available):
        self.emit("available", piston_available)

    def query_available_for_me(self, oauth_token, openid_identifier):
        pass


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
    #scagent.query_available_for_me("dummy_oauth", "dummy openid")

    gtk.main()
