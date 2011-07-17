from gi.repository import Gtk, Gdk, GdkPixbuf

from math import pi

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.drawing import rounded_rect


class FlowableGrid(Gtk.Fixed):

    def __init__(self):
        Gtk.Fixed.__init__(self)
        self.set_size_request(100, 100)

        self.row_spacing = 0
        self.column_spacing = 0
        self.n_columns = 0
        self.n_rows = 0

        self._cell_size = None
        self.connect("size-allocate", self.on_size_allocate)
        return

    # private
    def _get_n_columns_for_width(self, width, col_spacing):
        cell_w, cell_h = self.get_cell_size()
        n_cols = width / (cell_w + col_spacing)
        return n_cols

    def _layout_children(self, a):
        if not self.get_visible(): return

        #children = self.get_children()
        width = a.width

        col_spacing = self.column_spacing
        row_spacing = self.row_spacing

        cell_w, cell_h = self.get_cell_size()

        n_cols = self._get_n_columns_for_width(width, col_spacing)
        if n_cols == 0: return

        overhang = width - n_cols * (col_spacing + cell_w)
        xo = overhang / n_cols

        y = 0
        for i, child in enumerate(self.get_children()):
            x = a.x + (i % n_cols) * (cell_w + col_spacing + xo)
            if n_cols == 1:
                x += xo/2
            if (i%n_cols) == 0:
                y = a.y + (i / n_cols) * (cell_h + row_spacing)

            child_alloc = child.get_allocation()
            child_alloc.x = x
            child_alloc.y = y
            child_alloc.width = cell_w
            child_alloc.height = cell_h
            child.size_allocate(child_alloc)
        return

    # overrides
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_height_for_width(self, width):
        alloc = self.get_allocation()
        if width == alloc.width: alloc.height, alloc.height

        n_cols = self._get_n_columns_for_width(
                        width, self.column_spacing)

        if not n_cols: return alloc.height, alloc.height

        children = self.get_children()
        n_rows = len(children) / n_cols

        # store these for use when _layout_children gets called
        self.n_columns = n_cols
        self.n_rows = n_rows

        if len(children) % n_cols:
            n_rows += 1

        _, cell_h = self.get_cell_size()
        pref_h = n_rows * (cell_h + self.row_spacing)
        return pref_h, pref_h

    # signal handlers
    def on_size_allocate(self, *args):
        self._layout_children(self.get_allocation())
        return

    # public
    def add_child(self, child):
        self._cell_size = None
        self.put(child, 0, 0)
        return

    def get_cell_size(self):
        if self._cell_size is not None:
            return self._cell_size

        w = h = 1
        for child in self.get_children():
            child_pref_w = child.get_preferred_width()[0]
            child_pref_h = child.get_preferred_height()[0]
            w = max(w, child_pref_w)
            h = max(h, child_pref_h)

        self._cell_size = (w, h)
        return w, h

    def set_row_spacing(self, value):
        self.row_spacing = value
        self._layout_children(self.get_allocation())
        return

    def set_column_spacing(self, value):
        self.column_spacing = value
        self._layout_children(self.get_allocation())
        return

    def remove_all(self):
        self._cell_size = None
        for child in self.get_children():
            self.remove(child)
        return


_frame_asset_cache = {}
class Frame(Gtk.Alignment):

    BORDER_IMAGE = "softwarecenter/ui/gtk3/art/frame-border-image.png"
    CORNER_LABEL = "softwarecenter/ui/gtk3/art/corner-label.png"

    def __init__(self, padding=3, border_radius=5):
        Gtk.Alignment.__init__(self)
        self.set_padding(padding, padding, padding, padding)

        # corner lable jazz
        self.show_corner_label = False
        self.layout = self.create_pango_layout("")

        assets = self._cache_art_assets()
        self.connect("draw", self.on_draw, border_radius, assets)
        self.connect_after("draw", self.on_draw_after,
                           assets, self.layout)
        return

    def _cache_art_assets(self):
        import cairo
        global _frame_asset_cache
        assets = _frame_asset_cache
        if assets: return assets

        def cache_corner_surface(tag, xo, yo):
            sw = sh = cnr_slice
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
            cr = cairo.Context(surf)
            cr.set_source_surface(border_image, xo, yo)
            cr.paint()
            assets[tag] = surf
            del cr
            return

        def cache_edge_pattern(tag, xo, yo, sw, sh):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, sw, sh)
            cr = cairo.Context(surf)
            cr.set_source_surface(border_image, xo, yo)
            cr.paint()
            ptrn = cairo.SurfacePattern(surf)
            ptrn.set_extend(cairo.EXTEND_PAD)
            assets[tag] = ptrn
            del cr
            return

        # the basic stuff
        border_image = cairo.ImageSurface.create_from_png(self.BORDER_IMAGE)
        assets["corner-slice"] = cnr_slice = 10
        w = border_image.get_width()
        h = border_image.get_height()

        # caching ....
        # north-west corner of border image
        cache_corner_surface("nw", 0, 0)
        # northern edge pattern
        cache_edge_pattern("n",
                           -cnr_slice, 0,
                           w-2*cnr_slice, cnr_slice)
        # north-east corner
        cache_corner_surface("ne", -(w-cnr_slice), 0)
        # eastern edge pattern
        cache_edge_pattern("e",
                           -(w-cnr_slice), -cnr_slice,
                           cnr_slice, h-2*cnr_slice)
        # south-east corner
        cache_corner_surface("se", -(w-cnr_slice), -(h-cnr_slice))
        # southern edge pattern
        cache_edge_pattern("s",
                           -cnr_slice, -(h-cnr_slice),
                           w-2*cnr_slice, cnr_slice)
        # south-west corner
        cache_corner_surface("sw", 0, -(h-cnr_slice))
        # western edge pattern
        cache_edge_pattern("w", 0, -cnr_slice, cnr_slice, h-2*cnr_slice)

        # all done!
        return assets

    def on_draw(self, widget, cr, border_radius, assets):
        a = widget.get_allocation()
        width = a.width
        height = a.height
        cnr_slice = assets["corner-slice"]

        # paint north-west corner
        cr.set_source_surface(assets["nw"], 0, 0)
        cr.paint()

        # paint north length
        cr.save()
        cr.set_source(assets["n"])
        cr.rectangle(cnr_slice, 0, width-2*cnr_slice, cnr_slice)
        cr.clip()
        cr.paint()
        cr.restore()

        # paint north-east corner
        cr.set_source_surface(assets["ne"], width-cnr_slice, 0)
        cr.paint()

        # paint east length
        cr.save()
        cr.translate(width-cnr_slice, cnr_slice)
        cr.set_source(assets["e"])
        cr.rectangle(0, 0, cnr_slice, height-2*cnr_slice)
        cr.clip()
        cr.paint()
        cr.restore()

        # paint south-east corner
        cr.set_source_surface(assets["se"], width-cnr_slice, height-cnr_slice)
        cr.paint()

        # paint south length
        cr.save()
        cr.translate(cnr_slice, height-cnr_slice)
        cr.set_source(assets["s"])
        cr.rectangle(0, 0, width-2*cnr_slice, cnr_slice)
        cr.clip()
        cr.paint()
        cr.restore()

        # paint south-west corner
        cr.set_source_surface(assets["sw"], 0, height-cnr_slice)
        cr.paint()

        # paint west length
        cr.save()
        cr.translate(0, cnr_slice)
        cr.set_source(assets["w"])
        cr.rectangle(0, 0, cnr_slice, height-2*cnr_slice)
        cr.clip()
        cr.paint()
        cr.restore()

        # fill interior
        rounded_rect(cr, 3, 2, a.width-6, a.height-6, border_radius)
        cr.set_source_rgba(1,1,1,0.75)
        cr.fill()
        return

    def on_draw_after(self, widget, cr, assets, layout):
        if not self.show_corner_label: return
        surf = assets["corner-label"]
        w = surf.get_width()
        h = surf.get_height()
        cr.reset_clip()
        cr.rectangle(-4, -4, w+4, h+4)
        cr.clip()
        cr.set_source_surface(surf, -2, -3)
        cr.paint()

        ex = layout.get_pixel_extents()[1]
        cr.translate(w/2-12, h/2-12)
        cr.rotate(-pi*0.25)
        Gtk.render_layout(widget.get_style_context(), cr, -ex.width/2, -ex.height/2, layout)
        return

    def set_show_corner_label(self, show_label):
        if self.show_corner_label == show_label: return
        global _frame_asset_cache
        assets = _frame_asset_cache

        if "corner-label" not in assets:
            # cache corner label
            import cairo
            surf = cairo.ImageSurface.create_from_png(self.CORNER_LABEL)
            assets["corner-label"] = surf

        self.show_corner_label = show_label
        self.queue_draw()
        return

    def set_corner_label_markup(self, markup):
        markup = '<span font_desc="10" color="white"><b>%s</b></span>' % markup
        self.set_show_corner_label(True)
        self.layout.set_markup(markup, -1)
        self.queue_draw()
        return


class FramedBox(Frame):

    def __init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=0, padding=3):
        Frame.__init__(self, padding)
        self.box = Gtk.Box.new(orientation, spacing)
        self.add(self.box)
        return

    def pack_start(self, *args, **kwargs):
        return self.box.pack_start(*args, **kwargs)

    def pack_end(self, *args, **kwargs):
        return self.box.pack_end(*args, **kwargs)


# this is used in the automatic tests
def get_test_container_window():
    win = Gtk.Window()
    win.set_size_request(500, 300)
    f = FlowableGrid()

    import buttons

    for i in range(10):
        t = buttons.CategoryTile("test", "folder")
        f.add_child(t)

    scroll = Gtk.ScrolledWindow()
    scroll.add_with_viewport(f)

    win.add(scroll)
    win.show_all()

    win.connect("destroy", lambda x: Gtk.main_quit())
    return win

if __name__ == '__main__':
    win = get_test_container_window()
    win.show_all()
    Gtk.main()
