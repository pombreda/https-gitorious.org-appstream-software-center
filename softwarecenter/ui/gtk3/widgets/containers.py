from gi.repository import Gtk


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
