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

import softwarecenter.paths
from spawn_helper import SpawnHelper

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
    
    def __init__(self, xid=None):
        GObject.GObject.__init__(self)

    def query_recommend_top(self):
        # build the command
        spawner = SpawnHelper()
        spawner.parent_xid = self.xid
        spawner.connect("data-available", self._on_recommend_top_data)
        spawner.connect("error", lambda spawner, err: self.emit("error", err))
        spawner.run_generic_piston_helper(
            "SoftwareCenterRecommenderAPI", "recommend_top")

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
