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
from gi.repository import GdkPixbuf

from softwarecenter.utils import SimpleFileDownloader


class Exhibit(Gtk.EventBox):
    """ a single exhibit ui element """

    __gsignals__ = {
        "clicked" : (GObject.SignalFlags.RUN_LAST,
                     None, 
                     (),
                     )
        }

    def __init__(self, exhibit, right_pixel_cutoff=0):
        Gtk.EventBox.__init__(self)
        self.fixed = Gtk.Fixed()
        self.image = Gtk.Image()
        self.label = Gtk.Label()
        self.downloader = SimpleFileDownloader()
        self.downloader.connect(
            "file-download-complete", self._on_file_download_complete)
        self.add(self.fixed)
        self.exhibit = None
        self.set_right_pixel_cutoff(right_pixel_cutoff)
        self._init_event_handling()
        self._set_exhibit(exhibit)

    def set_right_pixel_cutoff(self, right_pixel_cutoff):
        self.right_pixel_cutoff=right_pixel_cutoff
        
    def _set_exhibit(self, exhibit):
        self.exhibit_data = exhibit
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
        
    def _init_event_handling(self):
        self.set_property("can-focus", True)
        self.set_events(Gdk.EventMask.BUTTON_RELEASE_MASK|
                        Gdk.EventMask.ENTER_NOTIFY_MASK|
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)

        self.connect("enter-notify-event", self._on_enter_notify)
        self.connect("leave-notify-event", self._on_leave_notify)
        self.connect("button-release-event", self._on_button_release)

    def _on_enter_notify(self, widget, event):
        window = self.get_window()
        if window:
            window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))

    def _on_leave_notify(self, widget, event):
        window = self.get_window()
        if window:
            window.set_cursor(None)

    def _on_button_release(self, widget, event):
        if event.button != 1:
            return
        self.emit("clicked")

    def _on_file_download_complete(self, downloader, path):
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        pb = pb.scale_simple(600, 200, GdkPixbuf.InterpType.BILINEAR)
        print pb.get_width(), pb.get_height()
        self.image.set_from_pixbuf(pb)

    def __repr__(self):
        return "<Exhibit: '%s'>" % (self.exhibit_data.title_translated)


class ExhibitBanner(Gtk.Fixed):

    __gsignals__ = {
        "show-exhibits" : (GObject.SignalFlags.RUN_LAST,
                           None, 
                           (GObject.TYPE_PYOBJECT,),
                           )
        }

    def __init__(self):
        Gtk.Fixed.__init__(self)
        self.exhibits = []

    def set_exhibits(self, exhibits_list):
        for exhibit_data in exhibits_list:
            exhibit = Exhibit(exhibit_data)
            exhibit.connect("clicked", self._on_exhibit_clicked)
            self.exhibits.append(exhibit)
        # now draw them in the self.exhibits order
        self._draw_exhibits()

    def _draw_exhibits(self):
        # remove the old ones
        self.foreach(lambda w,d: self.remove(w), None)

        # draw the new ones
        for (i, exhibit) in enumerate(reversed(self.exhibits)):
            # FIXME: we may need to put this to the right actually, in the spec
            #        the wireframe has it on the left, the mockup on the righ
            self.put(exhibit, i*20, 0)

    def _on_exhibit_clicked(self, exhibit):
        if self.exhibits[0] == exhibit:
            self.emit("show-exhibits", 
                      exhibit.exhibit_data.package_names.split(","))
        else:
            # exchange top with the clicked one
            self.exhibits[self.exhibits.index(exhibit)] = self.exhibits[0]
            self.exhibits[0] = exhibit
            self._draw_exhibits()


if __name__ == "__main__":
    from mock import Mock

    win = Gtk.Window()
    win.set_size_request(600, 400)

    exhibits_list = []

    for (i, (title, url)) in enumerate([
            ("1 some title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=orangeubuntulogo.png"),
            ("2 another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=blackeubuntulogo.png"),
            ("3 yet another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=xubuntu.png"),
            ]):
         exhibit = Mock()
         exhibit.background_color = "#000000"
         exhibit.banner_url = url
         exhibit.date_created = "2011-07-20 08:49:15"
         exhibit.font_color = "#000000"
         exhibit.font_name = ""
         exhibit.font_size = 24
         exhibit.id = i
         exhibit.package_names = "apt,2vcard"
         exhibit.published = True
         exhibit.title_coords = [10, 10]
         exhibit.title_translated = title
         exhibits_list.append(exhibit)

    exhibit_banner = ExhibitBanner()
    exhibit_banner.set_exhibits(exhibits_list)
    win.add(exhibit_banner)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
