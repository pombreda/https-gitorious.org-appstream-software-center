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

import sys
from gi.repository import GObject
import gtk
import logging
import pygst

pygst.require("0.10")
import gst

from gettext import gettext as _

LOG = logging.getLogger(__name__)

class VideoPlayer(gtk.VBox):

    __gproperties__ = {
        'uri' : (str, 'videouri', 'uri to play', "",
                 GObject.PARAM_READWRITE),
        }

    def __init__(self):
        super(VideoPlayer, self).__init__()
        self.uri = ""
        # gtk ui
        self.movie_window = gtk.DrawingArea()
        self.pack_start(self.movie_window)
        self.button = gtk.Button(_("Play"))
        self.pack_start(self.button, False)
        self.button.connect("clicked", self.on_play_clicked)
        # player
        self.player = gst.element_factory_make("playbin2", "player")
        # bus stuff
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect("message", self.on_message)
        bus.connect("sync-message::element", self.on_sync_message)

    def on_play_clicked(self, button):
        if self.button.get_label() == _("Play"):
            self.button.set_label("Stop")
            print self.uri
            self.player.set_property("uri", self.uri)
            self.player.set_state(gst.STATE_PLAYING)
        else:
            self.player.set_state(gst.STATE_NULL)
            self.button.set_label(_("Play"))
						
    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_EOS:
            self.player.set_state(gst.STATE_NULL)
            self.button.set_label(_("Play"))
        elif t == gst.MESSAGE_ERROR:
            self.player.set_state(gst.STATE_NULL)
            err, debug = message.parse_error()
            LOG.error("Error playing video: %s (%s)" % (err, debug))
            self.button.set_label(_("Play"))
            
    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        message_name = message.structure.get_name()
        if message_name == "prepare-xwindow-id":
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            gtk.gdk.threads_enter()
            imagesink.set_xwindow_id(self.movie_window.window.xid)
            gtk.gdk.threads_leave()	


if __name__ == "__main__":
    logging.basicConfig()
    gtk.gdk.threads_init()

    win = gtk.Window(gtk.WINDOW_TOPLEVEL)
    win.set_default_size(500, 400)
    win.connect("destroy", gtk.main_quit)
    player = VideoPlayer()
    win.add(player)
    if len(sys.argv) < 2:
        player.uri = "http://upload.wikimedia.org/wikipedia/commons/9/9b/Pentagon_News_Sample.ogg"
    else:
        player.uri = sys.argv[1]
    win.show_all()
    gtk.main()
