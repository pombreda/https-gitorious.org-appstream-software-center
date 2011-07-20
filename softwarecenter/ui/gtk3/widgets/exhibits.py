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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject

from softwarecenter.utils import SimpleFileDownloader

class ExhibitBanner(Gtk.EventBox):

    __gsignals__ = {
        "show-exhibits" : (GObject.SignalFlags.RUN_LAST,
                           None, 
                           (GObject.TYPE_PYOBJECT,),
                           )
        }

    def __init__(self):
        Gtk.EventBox.__init__(self)
        self.image = Gtk.Image()
        self.label = Gtk.Label()
        self.downloader = SimpleFileDownloader()
        self.downloader.connect(
            "file-download-complete", self._on_file_download_complete)
        # add the fixed layout to the eventbox
        self.fixed = Gtk.Fixed()
        self._init_event_handling()
        self.add(self.fixed)

    def _init_event_handling(self):
        self.set_property("can-focus", True)
        self.set_events(Gdk.EventMask.BUTTON_RELEASE_MASK|
                        Gdk.EventMask.ENTER_NOTIFY_MASK|
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.connect("enter-notify-event", self._on_enter_notify)
        self.connect("leave-notify-event", self._on_leave_notify)
        self.connect("button-release-event", self._on_button_release)

    def _on_enter_notify(self, widget, event):
        pass
    def _on_leave_notify(self, widget, event):
        pass
    def _on_button_release(self, widget, event):
        if event.button != 1:
            return
        self.emit("show-exhibits", 
                  self.current_exhibit.package_names.split(","))

    def _on_file_download_complete(self, downloader, path):
        self.image.set_from_file(path)

    def set_exhibit(self, exhibit):
        self.current_exhibit = exhibit
        # FIXME:
        # - set background color
        # background image first
        self.downloader.download_file(exhibit.banner_url, use_cache=True)
        self.fixed.put(self.image, 0, 0)
        # then label on top
        self.label.set_text(exhibit.title_translated)
        self.fixed.put(
            self.label, exhibit.title_coords[0], exhibit.title_coords[1])
        # FIXME: set font name, colors, size (that is not exposed in the API)

if __name__ == "__main__":
    from mock import Mock

    win = Gtk.Window()
    win.set_size_request(600, 400)

    exhibit = Mock()
    exhibit.background_color = "#000000"
    exhibit.banner_url = "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=orangeubuntulogo.png"
    exhibit.date_created = "2011-07-20 08:49:15"
    exhibit.font_color = "#000000"
    exhibit.font_name = ""
    exhibit.id = 1
    exhibit.package_names = "apt,2vcard"
    exhibit.published = True
    exhibit.title_coords = [10, 10]
    exhibit.title_translated = "Some title"

    exhibit_banner = ExhibitBanner()
    exhibit_banner.set_exhibit(exhibit)
    win.add(exhibit_banner)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
