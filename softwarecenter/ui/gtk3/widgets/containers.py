from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

from math import pi

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.drawing import rounded_rect


class FlowableGrid(Gtk.Fixed):

    MIN_HEIGHT = 100

    def __init__(self, paint_grid_pattern=True):
        Gtk.Fixed.__init__(self)
        self.set_size_request(100, -1)
        self.row_spacing = 0
        self.column_spacing = 0
        self.n_columns = 0
        self.n_rows = 0

        self._cell_size = None
        self.connect("size-allocate", self.on_size_allocate)
        if paint_grid_pattern:
            self.connect("draw", self.on_draw)
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
        height = a.height

        col_spacing = self.column_spacing
        row_spacing = self.row_spacing

        n_cols = self._get_n_columns_for_width(width, col_spacing)
        cell_w, cell_h = self.get_cell_size()
        cell_w = width/n_cols

        if n_cols == 0: return

        #~ h_overhang = width - n_cols*cell_w - (n_cols-1)*col_spacing
        #~ if n_cols > 1:
            #~ xo = h_overhang / (n_cols-1)
        #~ else:
            #~ xo = h_overhang


        y = 0
        for i, child in enumerate(self.get_children()):
            x = a.x + (i % n_cols) * (cell_w + col_spacing)

            #~ x = a.x + (i % n_cols) * (cell_w + col_spacing + xo)
            #~ if n_cols == 1:
                #~ x += xo/2
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
        pref_h = n_rows*cell_h + (n_rows-1)*self.row_spacing + 1
        pref_h = max(self.MIN_HEIGHT, pref_h)
        return pref_h, pref_h

    # signal handlers
    def on_size_allocate(self, *args):
        self._layout_children(self.get_allocation())
        return

    def on_draw(self, widget, cr):
        if not (self.n_columns and self.n_rows): return

        cr.save()
        a = widget.get_allocation()
        rounded_rect(cr, 0, 0, a.width, a.height-1, 4)
        cr.clip()
        cr.set_source_rgb(0.905882353,0.894117647,0.901960784) #E7E4E6
        cr.set_line_width(1)

        cell_w = a.width / self.n_columns
        cell_h = a.height / self.n_rows

        for i in range(self.n_columns):
            for j in range(self.n_rows):
                # paint checker if need be
                if not (i + j%2)%2:
                    cr.save()
                    cr.set_source_rgb(0.976470588, 0.956862745, 0.960784314) #F9F4F5
                    cr.rectangle(i*cell_w, j*cell_h, cell_w, cell_h)
                    cr.fill()
                    cr.restore()

                # paint rows
                if not j: continue
                cr.move_to(0, j*cell_h + 0.5)
                cr.rel_line_to(a.width-1, 0)
                cr.stroke()

            # paint columns
            if not i: continue
            cr.move_to(i*cell_w + 0.5, 0)
            cr.rel_line_to(0, a.height-1)
            cr.stroke()

        cr.restore()
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
        self.set_padding(padding-1, padding, padding, padding)

        # corner lable jazz
        self.show_corner_label = False
        self.layout = self.create_pango_layout("")
        self.layout.set_width(40960)
        self.layout.set_ellipsize(Pango.EllipsizeMode.END)

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
            ptrn.set_extend(cairo.EXTEND_REPEAT)
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
        cr.reset_clip()
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
        cr.set_source_rgb(0.992156863,0.984313725,0.988235294)  #FDFBFC
        cr.fill_preserve()
        cr.clip()
        return

    def on_draw_after(self, widget, cr, assets, layout):
        if not self.show_corner_label: return
        surf = assets["corner-label"]
        w = surf.get_width()
        h = surf.get_height()
        cr.reset_clip()
        # the following arbitrary adjustments are specific to the
        # corner-label.png image...

        # alter the to allow drawing outside of the widget bounds
        cr.rectangle(-4, -4, w+4, h+4)
        cr.clip()
        cr.set_source_surface(surf, -2, -3)
        cr.paint()
        # render label
        ex = layout.get_pixel_extents()[1]
        # transalate to the visual center of the corner-label
        cr.translate(19, 19)
        # rotate counter-clockwise
        cr.rotate(-pi*0.25)
        # paint normal markup
        Gtk.render_layout(widget.get_style_context(),
                          cr, -ex.width/2, -ex.height/2, layout)
        return

    def set_show_corner_label(self, show_label):
        if (not self.layout.get_text() and
            self.show_corner_label == show_label): return
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

    def set_corner_label(self, markup):
        markup = '<span font_desc="12" color="white"><b>%s</b></span>' % markup
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
