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
import os
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import GdkPixbuf
from gi.repository import WebKit

from softwarecenter.utils import SimpleFileDownloader
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.shapes import Circle
import softwarecenter.paths

_asset_cache = {}

EXHIBIT_HTML = """
<html><head>
<style type="text/css">
.banner_text {
font-size:1.7em;
color:white;
background:yellow;
padding: 0.2em;
text-shadow:0em 0em 0.075em black;
position:absolute;
top:30;
left:20;
}
.banner_subtext {
font-size:1.2em;
color:white;
padding: 1em;
text-shadow:0em 0em 0.075em black;
position:absolute;
top:90;
left:30;
}
</style>
</head><body>

<img style="position:absolute; top:0; left:0;" src="%(banner_url)s">
<div class="banner_text">%(title)s</div>
<div class="banner_subtext"> %(subtitle)s</div>

</body></html>
"""

class DefaultExhibit(object):
    def __init__(self):
        self.id = 0
        self.package_names = ""
        self.title_translated = "Default exhibit"
        self.published = True
        self.banner_url = "file://%s" % (os.path.abspath(os.path.join(softwarecenter.paths.datadir, "default_banner/fallback.png")))
        self.html = EXHIBIT_HTML % { 
            'banner_url' : self.banner_url,
            'title' : _("Welcome to the Ubuntu Software Center"),
            'subtitle' : _("Its a new day"),
      }
        # we should extract this automatically from the html
        #self.atk_name = _("Default Banner")
        #self.atk_description = _("You see this banner because you have no cached banners")

class FeaturedExhibit(object):
    def __init__(self):
        self.id = 0
        self.package_names = "armagetronad,calibre,cheese,homebank,stellarium,gimp,inkscape,blender,audacity,gufw,frozen-bubble,fretsonfire,moovida,liferea,arista,gtg,freeciv-client-gtk,supertuxkart,tumiki-fighters,tuxpaint,webservice-office-zoho"
        self.title_translated = "Featured exhibit"
        self.published = True
        self.banner_url = "file://%s" % (os.path.abspath(os.path.join(softwarecenter.paths.datadir, "default_banner/fallback2.png")))
        self.html = EXHIBIT_HTML % { 
            'banner_url' : self.banner_url,
            'title' : _("Stuff we like"),
            'subtitle' : _("Its just great, try it!"),
      }
        # we should extract this automatically from the html
        #self.atk_name = _("Default Banner")
        #self.atk_description = _("You see this banner because you have no cached banners")


class _HtmlRenderer(Gtk.OffscreenWindow):

    __gsignals__ = {
        "render-finished" : (GObject.SignalFlags.RUN_LAST,
                            None, 
                            (),
                           )
        }


    def __init__(self):
        Gtk.OffscreenWindow.__init__(self)
        self.view = WebKit.WebView()
        settings = self.view.get_settings()
        settings.set_property("enable-java-applet", False)
        settings.set_property("enable-plugins", False)
        settings.set_property("enable-scripts", False)
        self.view.set_size_request(-1, ExhibitBanner.MAX_HEIGHT)
        self.add(self.view)
        self.show_all()
        self.loader = SimpleFileDownloader()
        self.loader.connect("file-download-complete",
                            self.on_download_complete)
        self.exhibit = None
        self.view.connect("notify::load-status", self._on_load_status)
        return

    def _on_load_status(self, view, prop):
        if view.get_property("load-status") ==  WebKit.LoadStatus.FINISHED:
            # this needs to run with a timeout because otherwise the 
            # status is emited before the offscreen image is finihsed
            GObject.timeout_add(1, lambda: self.emit("render-finished"))

    def on_download_complete(self, loader, path):
        image_name = os.path.basename(path)
        cache_dir = os.path.dirname(path)
        if hasattr(self.exhibit, "html") and self.exhibit.html:
            html = self.exhibit.html
        else:
            html = EXHIBIT_HTML % { 'banner_url' : self.exhibit.banner_url,
                                    'title' : self.exhibit.title_translated,
                                    'subtitle' : "",
                                    }
        html = html.replace(self.exhibit.banner_url, image_name)
        self.view.load_string(html, "text/html", "UTF-8", 
                              "file:///%s/" % cache_dir)
        return

    def set_exhibit(self, exhibit):
        self.exhibit = exhibit
        self.loader.download_file(exhibit.banner_url, 
                                  use_cache=True,
                                  simple_quoting_for_webkit=True)
        return 


class ExhibitButton(Gtk.Button):

    def __init__(self):
        Gtk.Button.__init__(self)
        self.DROPSHADOW = GdkPixbuf.Pixbuf.new_from_file(
            os.path.join(softwarecenter.paths.datadir,
                         "ui/gtk3/art/circle-dropshadow.png"))
        self.set_focus_on_click(False)
        self.set_name("exhibit-button")
        self._dropshadow = None
        # is the current active "page"
        self.is_active = False
        self.connect("size-allocate", self.on_size_allocate)

    def on_size_allocate(self, *args):
        a = self.get_allocation()
        if (self._dropshadow is not None and
            a.width == self._dropshadow.get_width() and
            a.height == self._dropshadow.get_height()):
            return

        self._dropshadow = self.DROPSHADOW.scale_simple(
                        a.width, a.width, GdkPixbuf.InterpType.BILINEAR)
        self._margin = int(float(a.width) / self.DROPSHADOW.get_width() * 15)
        return

    def do_draw(self, cr):
        a = self.get_allocation()
        #state = self.get_state_flags()
        context = self.get_style_context()

        ds_h = self._dropshadow.get_height()
        y = (a.height - ds_h) / 2
        Gdk.cairo_set_source_pixbuf(cr, self._dropshadow, 0, y)
        cr.paint()
        Circle.layout(cr, self._margin, (a.height-ds_h)/2 + self._margin,
                      a.width-2*self._margin,
                      a.width-2*self._margin)
        if self.is_active:
            color = context.get_background_color(Gtk.StateFlags.SELECTED)
        else:
            color = context.get_background_color(Gtk.StateFlags.INSENSITIVE)

        Gdk.cairo_set_source_rgba(cr, color)
        cr.fill()

        for child in self: 
            self.propagate_draw(child, cr)
        return


class ExhibitArrowButton(ExhibitButton):

    def __init__(self, arrow_type, shadow_type=Gtk.ShadowType.IN):
        ExhibitButton.__init__(self)
        a = Gtk.Alignment()
        a.set_padding(1,1,1,1)
        a.add(Gtk.Arrow.new(arrow_type, shadow_type))        
        self.add(a)
        return


class ExhibitBanner(Gtk.EventBox):

    __gsignals__ = {
        "show-exhibits-clicked" : (GObject.SignalFlags.RUN_LAST,
                           None, 
                           (GObject.TYPE_PYOBJECT,),
                           )
        }

    DROPSHADOW_HEIGHT = 11
    MAX_HEIGHT = 200 # pixels
    TIMEOUT_SECONDS = 15

    def __init__(self):
        Gtk.EventBox.__init__(self)
        vbox = Gtk.VBox()
        vbox.set_border_width(StockEms.SMALL)
        self.add(vbox)

        # defined to make overriding softwarecenter.paths.datadir possible
        self.NORTHERN_DROPSHADOW = os.path.join(
            softwarecenter.paths.datadir,
            "ui/gtk3/art/exhibit-dropshadow-n.png")
        self.SOUTHERN_DROPSHADOW = os.path.join(
            softwarecenter.paths.datadir,
            "ui/gtk3/art/exhibit-dropshadow-s.png")
        self.FALLBACK = os.path.join(
            softwarecenter.paths.datadir,
            "default_banner/fallback.png")

        hbox = Gtk.HBox(spacing=StockEms.SMALL)
        vbox.pack_end(hbox, False, False, 0)

        next = ExhibitArrowButton(Gtk.ArrowType.RIGHT)
        previous = ExhibitArrowButton(Gtk.ArrowType.LEFT)
        self.nextprev_hbox = Gtk.HBox()
        self.nextprev_hbox.pack_start(previous, False, False, 0)
        self.nextprev_hbox.pack_start(next, False, False, 0)
        hbox.pack_end(self.nextprev_hbox, False, False, 0)

        self.index_hbox = Gtk.HBox(spacing=StockEms.SMALL)
        alignment = Gtk.Alignment.new(1.0, 1.0, 0.0, 1.0)
        alignment.add(self.index_hbox)
        hbox.pack_end(alignment, False, False, 0)

        self.cursor = 0
        self._timeout = 0

        self.alpha = 1.0
        self.image = None 
        self.old_image = None 
        self.renderer = _HtmlRenderer()
        self.renderer.connect("render-finished", self.on_banner_rendered)

        self.set_visible_window(False)
        self.set_size_request(-1, self.MAX_HEIGHT)
        self.exhibits = []

        next.connect('clicked', self.on_next_clicked)
        previous.connect('clicked', self.on_previous_clicked)

        self._dotsigs = []

        self._cache_art_assets()
        self._init_event_handling()

    def _init_event_handling(self):
        self.set_can_focus(True)
        self.set_events(Gdk.EventMask.BUTTON_RELEASE_MASK|
                        Gdk.EventMask.ENTER_NOTIFY_MASK|
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)
        #~ self.connect("enter-notify-event", self.on_enter_notify)
        #~ self.connect("leave-notify-event", self.on_leave_notify)
        self.connect("button-release-event", self.on_button_release)

    def on_enter_notify(self, *args):
        return

    def on_leave_notify(self, *args):
        return

    def on_button_release(self, *args):
        exhibit = self.exhibits[self.cursor]
        print exhibit.package_names, exhibit
        if exhibit.package_names:
            self.emit("show-exhibits", exhibit)
        return

    def on_next_clicked(self, *args):
        self.next()
        self.queue_next()
        return

    def on_previous_clicked(self, *args):
        self.previous()
        self.queue_next()
        return

    def cleanup_timeout(self):
        if self._timeout > 0:
            GObject.source_remove(self._timeout)
            self._timeout = 0
        return

    def _render_exhibit_at_cursor(self):
        # copy old image for the fade
        if self.image:
            self.old_image = self.image.copy()
        # set the rigth one
        self.renderer.set_exhibit(self.exhibits[self.cursor])
        # make sure the active button is having a different color
        for i, w in enumerate(self.index_hbox):
            w.is_active = (i == self.cursor)

    def on_paging_dot_clicked(self, dot, index):
        self.cursor = index
        self._render_exhibit_at_cursor()

    def next(self):
        if len(self.exhibits)-1 == self.cursor:
            self.cursor = 0
        else:
            self.cursor += 1
        self._render_exhibit_at_cursor()
        return False

    def previous(self):
        if self.cursor == 0:
            self.cursor = len(self.exhibits)-1
        else:
            self.cursor -= 1
        self._render_exhibit_at_cursor()
        return False

    def queue_next(self):
        self.cleanup_timeout()
        self._timeout = GObject.timeout_add_seconds(
                                    self.TIMEOUT_SECONDS, self.next)
        return self._timeout

    def on_banner_rendered(self, renderer):
        self.image = renderer.get_pixbuf()

        if self.image.get_width() == 1:
            # the offscreen window is not really as such content not
            # correctly rendered
            GObject.timeout_add(500, self.on_banner_rendered, renderer)
            return

        self._fade_in()
        self.queue_next()
        return False

    def _fade_in(self, step=0.05):
        self.alpha = 0.0

        def fade_step():
            retval = True
            self.alpha += step

            if self.alpha >= 1.0:
                self.alpha = 1.0
                self.old_image = None
                retval = False

            self.queue_draw()
            return retval

        GObject.timeout_add(50, fade_step)
        return

    def _cache_art_assets(self):
        global _asset_cache
        assets = _asset_cache
        if assets: 
            return assets

        #~ surf = cairo.ImageSurface.create_from_png(self.NORTHERN_DROPSHADOW)
        #~ ptrn = cairo.SurfacePattern(surf)
        #~ ptrn.set_extend(cairo.EXTEND_REPEAT)
        #~ assets["n"] = ptrn

        surf = cairo.ImageSurface.create_from_png(self.SOUTHERN_DROPSHADOW)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["s"] = ptrn
        return assets

    def do_draw(self, cr):

        # hide the next/prev buttons if needed
        if len(self.exhibits) == 1:
            self.nextprev_hbox.hide()
        else:
            self.nextprev_hbox.show()

        # do the actual drawing
        cr.save()

        a = self.get_allocation()

        cr.set_source_rgb(1,1,1)
        cr.paint()

        if self.old_image is not None:
            #x = (a.width - self.old_image.get_width()) / 2
            x = 0
            y = 0
            Gdk.cairo_set_source_pixbuf(cr, self.old_image, x, y)
            cr.paint()

        if self.image is not None:
            #x = (a.width - self.image.get_width()) / 2
            x = 0
            y = 0
            Gdk.cairo_set_source_pixbuf(cr, self.image, x, y)
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
        cr.set_source(_asset_cache["s"])
        cr.paint()
        cr.restore()

        cr.set_line_width(1)
        cr.move_to(-0.5, a.height-0.5)
        cr.rel_line_to(a.width+1, 0)
        cr.set_source_rgba(1,1,1,0.75)
        cr.stroke()

        cr.restore()

        for child in self: 
            self.propagate_draw(child, cr)
        return

    def set_exhibits(self, exhibits_list):
        self.exhibits = exhibits_list
        self.cursor = 0

        for child in self.index_hbox:
            child.destroy()

        for sigid in self._dotsigs:
            GObject.source_remove(sigid)

        self._dotsigs = []
        for i, exhibit in enumerate(self.exhibits):
            dot = ExhibitButton()
            dot.set_size_request(StockEms.LARGE, StockEms.LARGE)
            self._dotsigs.append(
                dot.connect("clicked",
                            self.on_paging_dot_clicked,
                            len(self.exhibits) - 1 - i) # index
            )
            self.index_hbox.pack_end(dot, False, False, 0)
            self.index_hbox.show_all()

        self._render_exhibit_at_cursor()
        return

def get_test_exhibits_window():
    from mock import Mock

    win = Gtk.Window()
    win.set_size_request(600, 200)

    exhibit_banner = ExhibitBanner()

    exhibits_list = [DefaultExhibit()]
    for (i, (title, url)) in enumerate([
            ("1 some title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=orangeubuntulogo.png"),
            ("2 another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=blackeubuntulogo.png"),
            ("3 yet another title", "https://wiki.ubuntu.com/Brand?action=AttachFile&do=get&target=xubuntu.png"),
            ]):
         exhibit = Mock()
         exhibit.id = i
         exhibit.package_names = "apt,2vcard"
         exhibit.published = True
         exhibit.style = "some uri to html"
         exhibit.title_translated = title
         exhibit.banner_url = url
         exhibit.html = None
         exhibits_list.append(exhibit)

    exhibit_banner.set_exhibits(exhibits_list)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(exhibit_banner)
    win.add(scroll)

    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    return win

if __name__ == "__main__":
    softwarecenter.paths.datadir = "./data"
    win = get_test_exhibits_window()
    Gtk.main()
