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

import cairo

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GdkPixbuf
from gi.repository import WebKit

from softwarecenter.utils import SimpleFileDownloader
from softwarecenter.ui.gtk3.em import em


class _HtmlRenderer(Gtk.OffscreenWindow):

    def __init__(self):
        Gtk.OffscreenWindow.__init__(self)
        self.set_size_request(-1, ExhibitBanner.MAX_HEIGHT)
        self.view = WebKit.WebView()
        self.view.load_uri("http://dl.dropbox.com/u/123544/banner-test.html")
        self.add(self.view)
        self.show_all()
        return


class Exhibit(object):

    attrs = {}

    def __init__(self, banner, attrs):
        pass
        #~ self.banner = banner
        #~ self.attrs = attrs
        #~ self.image = None
#~ 
        #~ self._parse_colors(attrs)
        #~ self._parse_markup(attrs)
#~ 
        #~ self.downloader = SimpleFileDownloader()
        #~ self.downloader.connect(
            #~ "file-download-complete", self._on_file_download_complete)
        #~ self.downloader.download_file(attrs.banner_url, use_cache=False)
        #~ return
#~ 
    #~ def _parse_colors(self, attrs):
        #~ # translate colours into Gdk.RGBA's
        #~ rgba = Gdk.RGBA()
        #~ rgba.parse(attrs.background_color)
        #~ self.background_color = rgba
        #~ return
#~ 
    #~ def _parse_markup(self, attrs):
        #~ font_desc = "%s %s" % (attrs.font_name or "Ubuntu",
                               #~ attrs.font_size or 12)
#~ 
        #~ markup = '<span font_desc="%s" color="%s">%s</span>'
        #~ markup = markup % (font_desc,
                           #~ attrs.font_color or '#000',
                           #~ attrs.title_translated)
#~ 
        #~ self.layout = self.banner.create_pango_layout('')
        #~ self.layout.set_markup(markup, -1)
        #~ self.layout.xy = attrs.title_coords
        #~ return
#~ 
    #~ def _get_scaled_pixbuf(self, pb, width, height):
        #~ sf = float(ExhibitBanner.MAX_HEIGHT) / height
        #~ pb = pb.scale_simple(int(width*sf), ExhibitBanner.MAX_HEIGHT,
                             #~ GdkPixbuf.InterpType.BILINEAR)
        #~ return pb
#~ 
    #~ def _on_file_download_complete(self, downloader, path):
        #~ pb = GdkPixbuf.Pixbuf.new_from_file(path)
        #~ width, height = pb.get_width(), pb.get_height()

        if height != ExhibitBanner.MAX_HEIGHT:
            pb = self._get_scaled_pixbuf(pb, width, height)
#~ 
        #~ self.image = pb
        #~ self.banner.queue_draw()
        #~ return


#~ class Exhibit(Gtk.EventBox):
    #~ """ a single exhibit ui element """
#~ 
    #~ __gsignals__ = {
        #~ "clicked" : (GObject.SignalFlags.RUN_LAST,
                     #~ None, 
                     #~ (),
                     #~ )
        #~ }
#~ 
    #~ def __init__(self, exhibit, right_pixel_cutoff=0):
        #~ Gtk.EventBox.__init__(self)
        #~ self.fixed = Gtk.Fixed()
        #~ self.image = Gtk.Image()
        #~ self.label = Gtk.Label()
        #~ self.downloader = SimpleFileDownloader()
        #~ self.downloader.connect(
            #~ "file-download-complete", self._on_file_download_complete)
        #~ self.add(self.fixed)
        #~ self.exhibit = None
        #~ self.set_right_pixel_cutoff(right_pixel_cutoff)
        #~ self._init_event_handling()
        #~ self._set_exhibit(exhibit)
        #~ self.connect("draw", self.on_draw)
#~ 
    #~ def on_draw(self, widget, cr):
        #~ Gdk.cairo_set_source_rgba(cr, self.bgcolor)
        #~ cr.paint()
        #~ return
#~ 
    #~ def set_right_pixel_cutoff(self, right_pixel_cutoff):
        #~ self.right_pixel_cutoff=right_pixel_cutoff
        #~ 
    #~ def _set_exhibit(self, exhibit):
        #~ self.exhibit_data = exhibit
        #~ self.bgcolor = Gdk.RGBA()
        #~ self.bgcolor.parse(exhibit.background_color)
        #~ # FIXME:
        #~ # - set background color
        #~ # background image first
        #~ self.downloader.download_file(exhibit.banner_url, use_cache=True)
        #~ self.fixed.put(self.image, 0, 0)
        #~ # then label on top
        #~ self.label.set_text(exhibit.title_translated)
        #~ self.fixed.put(
            #~ self.label, exhibit.title_coords[0], exhibit.title_coords[1])
        #~ # FIXME: set font name, colors, size (that is not exposed in the API)
#~ 
    #~ def _init_event_handling(self):
        #~ self.set_property("can-focus", True)
        #~ self.set_events(Gdk.EventMask.BUTTON_RELEASE_MASK|
                        #~ Gdk.EventMask.ENTER_NOTIFY_MASK|
                        #~ Gdk.EventMask.LEAVE_NOTIFY_MASK)
#~ 
        #~ self.connect("enter-notify-event", self._on_enter_notify)
        #~ self.connect("leave-notify-event", self._on_leave_notify)
        #~ self.connect("button-release-event", self._on_button_release)
#~ 
    #~ def _on_enter_notify(self, widget, event):
        #~ window = self.get_window()
        #~ if window:
            #~ window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND2))
#~ 
    #~ def _on_leave_notify(self, widget, event):
        #~ window = self.get_window()
        #~ if window:
            #~ window.set_cursor(None)
#~ 
    #~ def _on_button_release(self, widget, event):
        #~ if event.button != 1:
            #~ return
        #~ self.emit("clicked")

    #~ def _get_scaled_pixbuf(self, pb, width, height):
        #~ sf = float(ExhibitBanner.MAX_HEIGHT) / height
        #~ pb = pb.scale_simple(int(width*sf), ExhibitBanner.MAX_HEIGHT,
                             #~ GdkPixbuf.InterpType.BILINEAR)
        #~ print pb.get_width(), pb.get_height()
        #~ return pb
 
    #~ def _on_file_download_complete(self, downloader, path):
        #~ pb = GdkPixbuf.Pixbuf.new_from_file(path)
        #~ width, height = pb.get_width(), pb.get_height()
#~ 
        #~ if height != ExhibitBanner.MAX_HEIGHT:
            #~ pb = self._get_scaled_pixbuf(pb, width, height)
#~ 
        #~ self.image.set_from_pixbuf(pb)
#~ 
    #~ def __repr__(self):
        #~ return "<Exhibit: '%s'>" % (self.exhibit_data.title_translated)


class ExhibitButton(Gtk.Button):

    def __init__(self, arrow_type, shadow_type=Gtk.ShadowType.IN):
        Gtk.Button.__init__(self)
        self.set_size_request(24, 24)
        self.set_focus_on_click(False)

        self.set_name("exhibit-button")

        a = Gtk.Alignment()
        a.set_padding(2,2,2,2)
        a.add(Gtk.Arrow.new(arrow_type, shadow_type))
        self.add(a)


_asset_cache = {}
class ExhibitBanner(Gtk.EventBox):

    __gsignals__ = {
        "show-exhibits" : (GObject.SignalFlags.RUN_LAST,
                           None, 
                           (GObject.TYPE_PYOBJECT,),
                           )
        }

    NORTHERN_DROPSHADOW = "softwarecenter/ui/gtk3/art/exhibit-dropshadow-n.png"
    SOUTHERN_DROPSHADOW = "softwarecenter/ui/gtk3/art/exhibit-dropshadow-s.png"
    DROPSHADOW_HEIGHT = 11

    MAX_HEIGHT = 200 # pixels

    def __init__(self):
        Gtk.EventBox.__init__(self)
        hbox = Gtk.HBox()
        self.add(hbox)

        alignment = Gtk.Alignment.new(0.5, 0.5, 0.0, 0.0)
        alignment.set_padding(10, 10, 10, 10)
        alignment.add(ExhibitButton(Gtk.ArrowType.RIGHT))
        hbox.pack_end(alignment, False, False, 0)

        alignment = Gtk.Alignment.new(0.5, 0.5, 0.0, 0.0)
        alignment.set_padding(10, 10, 10, 10)
        alignment.add(ExhibitButton(Gtk.ArrowType.LEFT))
        hbox.pack_start(alignment, False, False, 0)

        self.alpha = 0.0
        self.image = None
        self.renderer = _HtmlRenderer()
        self.renderer.view.connect("load-finished",
                                   self.on_load, self.renderer)

        self.set_visible_window(False)
        self.set_size_request(-1, self.MAX_HEIGHT)
        self.exhibits = []

        assets = self._cache_art_assets()
        self.connect("draw", self.on_draw, assets)

    def on_load(self, view, frame, renderer):
        self.image = renderer.get_surface()
        self._fade_in()

    def _fade_in(self, step=0.1):
        self.alpha = 0.0

        def fade_step():
            retval = True
            self.alpha += step

            if self.alpha >= 1.0:
                self.alpha = 1.0
                retval = False

            self.queue_draw()
            return retval

        GObject.timeout_add(50, fade_step)
        return

    def _cache_art_assets(self):
        global _asset_cache
        assets = _asset_cache
        if assets: return assets

        surf = cairo.ImageSurface.create_from_png(self.NORTHERN_DROPSHADOW)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["n"] = ptrn

        surf = cairo.ImageSurface.create_from_png(self.SOUTHERN_DROPSHADOW)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["s"] = ptrn

        return assets

    def on_draw(self, widget, cr, assets):
        cr.save()

        a = widget.get_allocation()

        cr.set_source_rgb(1,1,1)
        cr.paint()

        if self.image is not None:
            x = (a.width - self.image.get_width()) / 2
            y = 0
            cr.set_source_surface(self.image, x, y)
            cr.paint_with_alpha(self.alpha)

        # paint dropshadows last
        #~ cr.rectangle(0, 0, a.width, self.DROPSHADOW_HEIGHT)
        #~ cr.clip()
        #~ cr.set_source(assets["n"])
        #~ cr.paint()
        #~ cr.reset_clip()
        cr.rectangle(0, a.height-self.DROPSHADOW_HEIGHT,
                     a.width, self.DROPSHADOW_HEIGHT)
        cr.clip()
        cr.save()
        cr.translate(0, a.height-self.DROPSHADOW_HEIGHT)
        cr.set_source(assets["s"])
        cr.paint()
        cr.restore()
        cr.restore()
        return

    def set_exhibits(self, exhibits_list):
        for exhibit_data in exhibits_list:
            exhibit = Exhibit(self, exhibit_data)
            #~ exhibit.connect("clicked", self._on_exhibit_clicked)
            self.exhibits.append(exhibit)
        #~ # now draw them in the self.exhibits order
        #~ self._draw_exhibits()
        return

    def _draw_exhibits(self):
        return

    #~ def _on_exhibit_clicked(self, exhibit):
        #~ if self.exhibits[0] == exhibit:
            #~ self.emit("show-exhibits", 
                      #~ exhibit.exhibit_data.package_names.split(","))
        #~ else:
            #~ # exchange top with the clicked one
            #~ self.exhibits[self.exhibits.index(exhibit)] = self.exhibits[0]
            #~ self.exhibits[0] = exhibit
            #~ self._draw_exhibits()


if __name__ == "__main__":
    from mock import Mock

    win = Gtk.Window()
    win.set_size_request(600, 400)

    exhibit_banner = ExhibitBanner()
    exhibits_list = []

    for (i, (title, url)) in enumerate([
            ("1 some title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=orangeubuntulogo.png"),
            ("2 another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=blackeubuntulogo.png"),
            ("3 yet another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=xubuntu.png"),
            ]):
         exhibit = Mock()
         exhibit.background_color = "#FFFFFF"
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

    exhibit_banner.set_exhibits(exhibits_list)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(exhibit_banner)
    win.add(scroll)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
