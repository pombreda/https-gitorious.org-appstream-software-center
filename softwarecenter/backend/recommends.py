#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2012 Canonical
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

from gi.repository import GObject
import logging
import os

import softwarecenter.paths
from softwarecenter.paths import PistonHelpers
from spawn_helper import SpawnHelper
from softwarecenter.i18n import get_language
from softwarecenter.distro import get_distro, get_current_arch

LOG = logging.getLogger(__name__)

class RecommenderAgent(GObject.GObject):

    __gsignals__ = {
        "recommend-top" : (GObject.SIGNAL_RUN_LAST,
                              GObject.TYPE_NONE, 
                              (GObject.TYPE_PYOBJECT,),
                             ),
        "error" : (GObject.SIGNAL_RUN_LAST,
                   GObject.TYPE_NONE, 
                   (str,),
                  ),
        }
    
    def __init__(self, ignore_cache=False, xid=None):
        GObject.GObject.__init__(self)
        self.ignore_cache = ignore_cache
        binary = os.path.join(
            softwarecenter.paths.datadir, PistonHelpers.RECOMMENDER_AGENT)
        self.HELPER_CMD = [binary]
        if self.ignore_cache:
            self.HELPER_CMD.append("--ignore-cache")
        #if xid:
        #    self.HELPER_CMD.append("--parent-xid")
        #    self.HELPER_CMD.append(str(xid))

    def query_recommend_top(self):
        # build the command
        cmd = self.HELPER_CMD[:] + ["recommend_top"]
        spawner = SpawnHelper()
        spawner.connect("data-available", self._on_recommend_top_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run(cmd)
    def _on_recommend_top_data(self, spawner, piston_top_apps):
        self.emit("recommend-top", piston_top_apps)

   
if __name__ == "__main__":
    from gi.repository import Gtk

    def _recommend_top(agent, top_apps):
        print ("_recommend_top: %s" % top_apps)
    def _error(agent, msg):
        print ("got a error: %s" % msg)
        Gtk.main_quit()

    # test specific stuff
    logging.basicConfig()
    softwarecenter.paths.datadir = "./data"

    agent = RecommenderAgent()
    agent.connect("recommend-top", _recommend_top)
    agent.connect("error", _error)
    agent.query_recommend_top()


    Gtk.main()
