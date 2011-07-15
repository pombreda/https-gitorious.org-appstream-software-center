import cairo

from gi.repository import Gtk

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.session.viewmanager import get_viewmanager
from softwarecenter.ui.gtk3.panes.viewswitcher import ViewSwitcher


class GlobalPane(Gtk.VBox):

    # art assets
    BACKGROUND = "softwarecenter/ui/gtk3/art/globalpane-bg.png"

    # colours
    LIGHT_AUBERGINE = "#d7d0d4"

    PADDING = StockEms.SMALL

    _asset_cache = {}


    def __init__(self, view_manager, datadir, db, cache, icons):
        Gtk.VBox.__init__(self)
        self.top_hbox = Gtk.HBox(spacing=StockEms.MEDIUM)
        self.top_hbox.set_border_width(self.PADDING)
        # add nav history back/forward buttons...
        # note:  this is hacky, would be much nicer to make the custom self/right
        # buttons in BackForwardButton to be Gtk.Activatable/Gtk.Widgets, then wire in the
        # actions using e.g. self.navhistory_back_action.connect_proxy(self.back_forward.left),
        # but couldn't seem to get this to work..so just wire things up directly
        vm = get_viewmanager()
        self.back_forward = vm.get_global_backforward()
        self.top_hbox.pack_start(self.back_forward, False, True, 0)

        self.view_switcher = ViewSwitcher(view_manager, datadir, db, cache, icons)
        self.top_hbox.pack_start(self.view_switcher, True, True, 0)

        #~ self.init_atk_name(self.searchentry, "searchentry")
        self.searchentry = vm.get_global_searchentry()
        self.top_hbox.pack_end(self.searchentry, False, True, 0)
        self.pack_start(self.top_hbox, False, True, 0)

        self._cache_art_assets()
        self.connect("draw", self.on_draw, self._asset_cache)
        return

    def _cache_art_assets(self):
        assets = self._asset_cache
        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.BACKGROUND)
        bg_ptrn = cairo.SurfacePattern(surf)
        bg_ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["bg"] = bg_ptrn
        return

    def on_draw(self, widget, cr, assets):
        a = widget.get_allocation()

        # paint bg
        cr.set_source(assets["bg"])
        cr.paint()

        # paint bottom edge highlight
        cr.set_line_width(1)
        cr.set_source_rgb(0.301960784, 0.301960784, 0.301960784) # grey
        cr.move_to(-0.5, a.height-1.5)
        cr.rel_line_to(a.width+1, 0)
        cr.stroke()

        # paint the bottom dark edge
        cr.set_source_rgb(0.141176471, 0.141176471, 0.141176471) # darkness
        cr.move_to(-0.5, a.height-0.5)
        cr.rel_line_to(a.width+1, 0)
        cr.stroke()
        return
