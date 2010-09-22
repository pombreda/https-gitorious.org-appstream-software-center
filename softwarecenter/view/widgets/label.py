import gtk
import pango
import gobject

from pango import SCALE as PS


class Layout(pango.Layout):


    TYPE_PARAGRAPH = 0
    TYPE_BULLET = 1


    def __init__(self, widget, text=''):
        pango.Layout.__init__(self, widget.get_pango_context())

        self.widget = widget
        self.length = 0
        self.char_width = -1
        self.format_type = self.TYPE_PARAGRAPH
        self.order_id = 0
        self.allocation = gtk.gdk.Rectangle(0,0,1,1)

        self.set_text(text)
        return

    def __len__(self):
        return self.length

    def set_text(self, text):
        pango.Layout.set_text(self, text)
        self.length = len(self.get_text())

    def set_allocation(self, x, y, w, h):
        self.allocation = gtk.gdk.Rectangle(x, y, w, h)
        return

    def set_width_chars(self, char_width):
        self.char_width = char_width
        if len(self.get_text()) > self.char_width:
            self.set_text(self.get_text()[:self.char_width])
            self.cursor_index = self.char_width
        return

    #def point_in(self, px, py):
        #a = self.allocation
        #wa = self.widget.allocation
        #px += wa.x
        #py += wa.y
        #r = gtk.gdk.region_rectangle(a)
        #return r.point_in(px, py)

    def index_at(self, px, py):
        wa = self.widget.allocation
        px += wa.x
        py += wa.y

        a = self.allocation
        if gtk.gdk.region_rectangle(a).point_in(px, py):
            return sum(self.xy_to_index((px-a.x)*PS, (py-a.y)*PS))
        return None

    def cursor_up(self, index):
        x, y = self.index_to_pos(index)[:2]
        y -= PS*self.widget.line_spacing
        return self.xy_to_index(x, y)

    def cursor_down(self, index):
        x, y = self.index_to_pos(index)[:2]
        y += PS*self.widget.line_spacing
        return self.xy_to_index(x, y)

    def highlight_all(self, cr):

        xo = self.allocation.x
        yo = self.allocation.y
        it = self.get_iter()
        self._highlight_all(cr, it, xo, yo)
        while it.next_line():
            self._highlight_all(cr, it, xo, yo)

    def highlight(self, cr, start, end):
        xo = self.allocation.x
        yo = self.allocation.y
        it = self.get_iter()
        self._highlight(cr, it, start, end, xo, yo)
        while it.next_line():
            self._highlight(cr, it, start, end, xo, yo)

    def _highlight(self, cr, it, start, end, xo, yo):
        l = it.get_line()
        ls = l.start_index
        le = ls + l.length
        #print (start, end), (ls, le)
        e = it.get_char_extents()

        if end < ls or start > le: return

        if start > ls and start <= le:
            x0 = l.index_to_x(start, 0)/PS
        else:
            x0 = 0
        if end >= ls and end < le:
             x1 = l.index_to_x(end, 0)/PS
        else:
            x1 = it.get_line_extents()[1][2]/PS

        cr.rectangle(x0+xo, e[1]/PS+yo, x1-x0, e[3]/PS)
        cr.fill()

    def _highlight_all(self, cr, it, xo, yo):
        x,y,w,h = map(lambda x: x/PS, it.get_line_extents()[1])
        cr.rectangle(xo+x, yo+y, w or 4, h)
        cr.fill()


class LabelCursor(object):

    def __init__(self):
        self.index = 0
        self.section = 0

    def __repr__(self):
        return 'Cursor: '+str((self.section, self.index))

    def get_rectangle(self, layout, a):
        x, y, w, h = layout.get_cursor_pos(self.index)[1]
        x = layout.allocation.x + x/PS - 1
        y = layout.allocation.y + y/PS
        return x, y, 1, h/PS

    def set_position(self, section, index):
        self.index = index
        self.section = section

    def get_position(self):
        return self.section, self.index

    def draw(self, cr, layout, a):
        cr.set_source_rgb(0,0,0)
        cr.rectangle(*self.get_rectangle(layout, a))
        cr.fill()
        return

    def zero(self):
        self.index = 0
        self.section = 0


class LabelSelection(object):

    def __init__(self, cursor):
        self.cursor = cursor
        self.index = 0
        self.section = 0

    def __repr__(self):
        return 'Selection: '+str(self.get_selection_range())

    def __nonzero__(self):
        c = self.cursor
        return (self.section, self.index) != (c.section, c.index)

    @property
    def min(self):
        c = self.cursor
        return min((self.section, self.index), (c.section, c.index))

    @property
    def max(self):
        c = self.cursor
        return max((self.section, self.index), (c.section, c.index))

    def clear(self):
        self.index = self.cursor.index
        self.section = self.cursor.section

    def set_position(self, section, index):
        self.index = index
        self.section = section

    def get_selection(self):
        return self.min, self.max


class FormattedLabel(gtk.EventBox):


    BULLET_POINT = u'  \u2022  '

    
    SELECT_LINE = 1
    SELECT_PARA = 2
    SELECT_ALL  = 3
    SELECT_FREE = 4


    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_redraw_on_allocate(False)
        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.POINTER_MOTION_MASK)

        self._bullet = self._new_layout()
        self._bullet.set_markup(self.BULLET_POINT)
        font_desc = pango.FontDescription()
        font_desc.set_weight(pango.WEIGHT_BOLD)
        self._bullet.set_font_description(font_desc)

        self.indent, self.vspacing = self._bullet.get_pixel_extents()[1][2:]
        self.cursor = LabelCursor()
        self.selection = LabelSelection(self.cursor)
        self.order = []

        self._sel_mode = self.SELECT_FREE
        self._xterm = gtk.gdk.Cursor(gtk.gdk.XTERM)
        self._highlight_rgb = (0,1,0)

        self.connect('size-allocate', self._on_allocate)
        self.connect('button-press-event', self._on_press)
        #self.connect('enter-notify-event', self._on_enter)
        #self.connect('leave-notify-event', self._on_leave)
        #self.connect('button-release-event', self._on_release)
        self.connect('motion-notify-event', self._on_motion)
        self.connect('style-set', self._on_style_set)
        return

    def _on_style_set(self, widget, old_style):
        c = self.style.base[gtk.STATE_SELECTED]
        self._highlight_rgb = c.red_float, c.green_float, c.blue_float
        return

    def _on_enter(self, widget, event):
        self.window.set_cursor(self._xterm)

    def _on_leave(self, widget, event):
        self.window.set_cursor(None)

    def _on_motion(self, widget, event):
        if not (event.state & gtk.gdk.BUTTON1_MASK): return
        self._sel_mode = self.SELECT_FREE
        for layout in self.order:
            index = layout.index_at(int(event.x), int(event.y))
            if index:
                self.selection.set_position(layout.order_id, index)
                self.queue_draw()
                break

    def _on_press(self, widget, event):
        self.grab_focus()
        if event.button != 1: return
        index = layout = None
        for layout in self.order:
            index = layout.index_at(int(event.x), int(event.y))
            if index:
                self.cursor.set_position(layout.order_id, index)
                if (event.type == gtk.gdk._2BUTTON_PRESS):
                    self._2click_select(self._sel_mode, layout, index)
                break
        return

    def _on_release(self, widget, event):
        print event.state, event.button
        return

    def _get_line_index_range(self, layout, i):
        keep_going = True
        it = layout.get_iter()
        while keep_going:
            l = it.get_line()
            ls = l.start_index
            le = ls + l.length
            if i >= ls and i <= le:
                return ls, le
            keep_going = it.next_line()
        return None

    def _2click_select(self, mode, layout, index):
        if mode == self.SELECT_FREE:
            print 'sel line'
            self._select_line(layout, index)
        elif mode == self.SELECT_LINE:
            print 'sel para'
            self._select_para(layout, index)
        elif mode == self.SELECT_PARA:
            print 'sel all'
            self._select_all(layout, index)
        else:
            # select none
            self._sel_mode = self.SELECT_FREE
            self.selection.clear()
            self.queue_draw()
        return

    def _select_line(self, layout, i):
        self._sel_mode = self.SELECT_LINE
        r = self._get_line_index_range(layout, i)
        if r:
            self.cursor.index = r[0]
            self.selection.index = r[1]
            self.selection.order_id = layout.order_id
            self.queue_draw()
        return

    def _select_para(self, layout, i):
        self._sel_mode = self.SELECT_PARA
        self.cursor.index = 0
        self.selection.index = len(layout)
        self.selection.order_id = layout.order_id
        self.queue_draw()
        return

    def _select_all(self, layout, index):
        self._sel_mode = self.SELECT_ALL
        layout1 = self.order[-1]
        self.cursor.index = 0
        self.cursor.section = 0
        self.selection.index = len(layout1)
        self.selection.section = layout1.order_id
        self.queue_draw()
        return

    def height_from_width(self, width):
        if not self.order: return
        height = 0
        for layout in self.order:
            if layout.format_type == Layout.TYPE_BULLET:
                layout.set_width(PS*(width-self.indent))
            else:
                layout.set_width(PS*width)
            height += layout.get_pixel_extents()[1][3] + self.vspacing
        return width, height - self.vspacing

    def _on_allocate(self, widget, a):
        if not self.order: return
        x = a.x
        y = a.y
        width = a.width
        for layout in self.order:
            lx,ly,lw,lh = layout.get_pixel_extents()[1]
            if layout.format_type == Layout.TYPE_BULLET:
                layout.set_allocation(x+lx+self.indent, y+ly, width-self.indent, lh)
            else:
                layout.set_allocation(x+lx, y+ly, width, lh)

            y += ly + lh + self.vspacing
        return

    def _new_layout(self):
        layout = Layout(self, '')
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_markup(self.BULLET_POINT)
        return layout

    def _highlight_selection(self, cr, i, start, end, layout):
        if i == start[0]:
            if end[0] > i:
                layout.highlight(cr, start[1], len(layout))
            else:
                layout.highlight(cr, start[1], end[1])

        elif i == end[0]:
            if start[0] < i:
                layout.highlight(cr, 0, end[1])
            else:
                layout.highlight(cr, start[1], end[1])

        else:
            layout.highlight_all(cr)

        return

    def draw(self, widget, event):
        if not self.order: return

        start, end = self.selection.get_selection()

        cr = widget.window.cairo_create()
        if self.has_focus():
            cr.set_source_rgb(*self._highlight_rgb)
        else:
            cr.set_source_rgb(0.8, 0.8, 0.8)

        for layout in self.order:
            la = layout.allocation
            i = layout.order_id

            if self.selection and i >= start[0] and i <= end[0]:
                self._highlight_selection(cr, i, start, end, layout)

            if layout.format_type == Layout.TYPE_BULLET:
                self._paint_bullet_point(self.allocation.x, la.y)

            # draw the layout
            self.style.paint_layout(self.window,    # gdk window
                                    self.state,     # state
                                    True,           # use text gc
                                    None,           # clip rectangle
                                    self,           # some gtk widget
                                    '',             # detail hint
                                    la.x,           # x coord
                                    la.y,           # y coord
                                    layout)         # a pango.Layout()
        # draw the cursor
        #c = self.cursor
        #c.draw(cr, self.order[c.section], a)
        return

    def _paint_bullet_point(self, x, y):
        # draw the layout
        self.style.paint_layout(self.window,    # gdk window
                                self.state,     # state
                                True,           # use text gc
                                None,           # clip rectangle
                                self,           # some gtk widget
                                '',             # detail hint
                                x,              # x coord
                                y,              # y coord
                                self._bullet)   # a pango.Layout()

    def append_paragraph(self, p):
        l = self._new_layout()
        l.format_type = Layout.TYPE_PARAGRAPH
        l.order_id = len(self.order)

        l.set_text(p)
        self.order.append(l)
        return

    def append_bullet(self, point):
        l = self._new_layout()
        l.format_type = Layout.TYPE_BULLET
        l.order_id = len(self.order)

        l.set_text(point)
        self.order.append(l)
        return

    def clear(self):
        self.cursor.zero()
        self.selection.clear()
        self.order = []
        return
