import cairo
import os

from gi.repository import Gtk, Gdk

import softwarecenter.paths

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.panes.viewswitcher import ViewSwitcher


class GlobalPane(Gtk.VBox):

    # art assets
    BACKGROUND = os.path.join(softwarecenter.paths.datadir,
                              "ui/gtk3/art/globalpane-bg.png")

    # colours
    LIGHT_AUBERGINE = "#d7d0d4"

    PADDING = StockEms.SMALL

    _asset_cache = {}

    def __init__(self, view_manager, datadir, db, cache, icons):
        Gtk.VBox.__init__(self)

        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, StockEms.LARGE, StockEms.LARGE)

        self.top_hbox = Gtk.HBox(spacing=StockEms.MEDIUM)
        alignment.add(self.top_hbox)
        # add nav history back/forward buttons...
        # note:  this is hacky, would be much nicer to make the custom self/right
        # buttons in BackForwardButton to be Gtk.Activatable/Gtk.Widgets, then wire in the
        # actions using e.g. self.navhistory_back_action.connect_proxy(self.back_forward.left),
        # but couldn't seem to get this to work..so just wire things up directly
        vm = get_viewmanager()
        self.back_forward = vm.get_global_backforward()
        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)
        a.add(self.back_forward)
        self.top_hbox.pack_start(a, False, True, 0)

        self.view_switcher = ViewSwitcher(view_manager, datadir, db, cache, icons)
        self.top_hbox.pack_start(self.view_switcher, True, True, 0)

        #~ self.init_atk_name(self.searchentry, "searchentry")
        self.searchentry = vm.get_global_searchentry()
        self.top_hbox.pack_end(self.searchentry, False, True, 0)
        self.pack_start(alignment, False, True, 0)

        self._cache_art_assets()
        self.connect("draw", self.on_draw, self._asset_cache)
        return

    def _cache_art_assets(self):
        assets = self._asset_cache

        # cache the bg color
        context = self.get_style_context()
        context.save()
        context.add_class("menu")
        color = context.get_background_color(Gtk.StateFlags.NORMAL)
        context.restore()
        assets["bg-color"] = color

        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.BACKGROUND)
        bg_ptrn = cairo.SurfacePattern(surf)
        bg_ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["bg"] = bg_ptrn
        return

    def on_draw(self, widget, cr, assets):
        a = widget.get_allocation()

        # paint bg base color
        Gdk.cairo_set_source_rgba(cr, assets["bg-color"])
        cr.paint()

        # paint diagonal lines
        #~ cr.save()
        #~ bg = assets["bg"]
        #~ surf_height = bg.get_surface().get_width() - 5
        #~ cr.rectangle(0, 0, a.width, surf_height)
        #~ cr.clip()
        #~ cr.set_source(bg)
        #~ cr.paint_with_alpha(0.3)
        #~ cr.restore()

        # paint bottom edge highlight
        #~ cr.set_line_width(1)
        #~ cr.set_source_rgb(0.301960784, 0.301960784, 0.301960784) # grey
        #~ cr.move_to(-0.5, a.height-1.5)
        #~ cr.rel_line_to(a.width+1, 0)
        #~ cr.stroke()
#~ 
        #~ # paint the bottom dark edge
        #~ cr.set_source_rgb(0.141176471, 0.141176471, 0.141176471) # darkness
        #~ cr.move_to(-0.5, a.height-0.5)
        #~ cr.rel_line_to(a.width+1, 0)
        #~ cr.stroke()
        return

def get_test_window():

    from softwarecenter.testutils import (get_test_db,
                                          get_test_datadir,
                                          get_test_gtk3_viewmanager,
                                          get_test_pkg_info,
                                          get_test_gtk3_icon_cache,
                                          )
    vm = get_test_gtk3_viewmanager()
    db = get_test_db()
    cache = get_test_pkg_info()
    datadir = get_test_datadir()
    icons = get_test_gtk3_icon_cache()

    p = GlobalPane(vm, datadir, db, cache, icons)

    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(p)
    win.show_all()
    return win

if __name__ == "__main__":

    win = get_test_window()
    
    Gtk.main()
