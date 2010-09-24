import gtk
import pango
import gobject

from pango import SCALE as PS
from gtk import keysyms as keys


class Layout(pango.Layout):

    def __init__(self, widget, text=''):
        pango.Layout.__init__(self, widget.get_pango_context())

        self.widget = widget
        self.length = 0
        self.char_width = -1
        self.indent = 0
        self.is_bullet = False
        self.order_id = 0
        self.allocation = gtk.gdk.Rectangle(0,0,1,1)
        self._default_attrs = True

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

    #def set_width_chars(self, char_width):
        #self.char_width = char_width
        #if len(self.get_text()) > self.char_width:
            #self.set_text(self.get_text()[:self.char_width])
            #self.cursor_index = self.char_width
        #return

    #def point_in(self, px, py):
        #a = self.allocation
        #wa = self.widget.allocation
        #px += wa.x
        #py += wa.y
        #r = gtk.gdk.region_rectangle(a)
        #return r.point_in(px, py)

    def cursor_up(self, cursor, target_x=-1):
        layout = self.widget.order[cursor.section]
        x, y = layout.index_to_pos(cursor.index)[:2]

        if target_x >= 0:
            x = target_x

        y -= PS*self.widget.line_height
        return sum(layout.xy_to_index(x, y)), (x, y)

    def cursor_down(self, cursor, target_x=-1):
        layout = self.widget.order[cursor.section]
        x, y = layout.index_to_pos(cursor.index)[:2]

        if target_x >= 0:
            x = target_x

        y += PS*self.widget.line_height
        return sum(layout.xy_to_index(x, y)), (x, y)

    def index_at(self, px, py):
        wa = self.widget.allocation
        px += wa.x
        py += wa.y

        a = self.allocation
        if gtk.gdk.region_rectangle(a).point_in(px, py):
            return sum(self.xy_to_index((px-a.x)*PS, (py-a.y)*PS))
        return None

    def reset_attrs(self, fg, bg):
        attrs = self.get_attributes()
        fgattr = pango.AttrForeground(fg.red, fg.green, fg.blue, 0, self.length)
        bgattr = pango.AttrBackground(bg.red, bg.green, bg.blue, 0, self.length)
        attrs.change(fgattr)
        attrs.change(bgattr)
        self.set_attributes(attrs)
        self._default_attrs = True
        return

    def highlight(self, start, end, colours):
        attrs = self.get_attributes()
        fg, bg = colours[:2]
        fgattr = pango.AttrForeground(fg.red, fg.green, fg.blue, 0, self.length)
        bgattr = pango.AttrBackground(bg.red, bg.green, bg.blue, 0, self.length)
        attrs.change(fgattr)
        attrs.change(bgattr)

        fg, bg = colours[2:]
        fgattr = pango.AttrForeground(fg.red, fg.green, fg.blue, start, end)
        bgattr = pango.AttrBackground(bg.red, bg.green, bg.blue, start, end)
        attrs.change(fgattr)
        attrs.change(bgattr)

        self.set_attributes(attrs)
        self._default_attrs = False
        return

    def highlight_all(self, colours):
        attrs = self.get_attributes()
        fg, bg = colours[2:]
        fgattr = pango.AttrForeground(fg.red, fg.green, fg.blue, 0, self.length)
        bgattr = pango.AttrBackground(bg.red, bg.green, bg.blue, 0, self.length)
        attrs.change(fgattr)
        attrs.change(bgattr)
        self.set_attributes(attrs)
        self._default_attrs = False
        return


class PrimaryCursor(object):

    WORD_TERMINATORS = (' ', ',', '.', ':', ';', '!', '?', '(', ')', '[', ']', '{', '}')

    def __init__(self, parent):
        self.parent = parent
        self.index = 0
        self.section = 0

    def __repr__(self):
        return 'Cursor: '+str((self.section, self.index))

    def set_order(self, order):
        self.order = order
        return

    def get_current_line(self):
        keep_going = True
        i, it = self.index, self.parent.order[self.section].get_iter()
        ln = 0 
        while keep_going:
            l = it.get_line()
            ls = l.start_index
            le = ls + l.length

            if i >= ls and i <= le:
                return (self.section, ln), (ls, le), l
            ln += 1
            keep_going = it.next_line()
        return None, None, None

    def get_current_word(self):
        keep_going = True
        layout = self.parent.order[self.section]
        text = layout.get_text()
        i, it = self.index, layout.get_iter()
        start = 0
        while keep_going:
            j = it.get_index()
            if j >= i and text[j] in self.WORD_TERMINATORS:
                return self.section, (start, j)

            elif text[j] in self.WORD_TERMINATORS:
                start = j+1

            keep_going = it.next_char()
        return None, None

    def get_rectangle(self, layout, a):
        if self.index < len(layout):
            x, y, w, h = layout.get_cursor_pos(self.index)[1]
        else:
            x, y, w, h = layout.get_cursor_pos(len(layout))[1]
        x = layout.allocation.x + x/PS
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


class SelectionCursor(object):

    SELECT_WORD   = 0
    SELECT_LINE   = 1
    SELECT_PARA   = 2
    SELECT_ALL    = 3
    SELECT_NORMAL = 4

    def __init__(self, cursor):
        self.cursor = cursor
        self.index = 0
        self.section = 0
        self.state = self.SELECT_NORMAL
        self.target_x = None
        self.target_x_indent = 0

    def __repr__(self):
        return 'Selection: '+str(self.get_range())

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
        self.target_x = None

    def set_position(self, section, index):
        self.index = index
        self.section = section

    def set_target_x(self, x, indent):
        self.target_x = x
        self.target_x_indent = indent
        return

    def get_position(self):
        return self.section, self.index

    def get_range(self):
        return self.min, self.max


class IndentLabel(gtk.EventBox):


    BULLET_POINT = u'  \u2022  '


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

        self.indent, self.line_height = self._bullet.get_pixel_extents()[1][2:]
        self.order = []
        self.cursor = PrimaryCursor(self)
        self.selection = SelectionCursor(self.cursor)

        self._xterm = gtk.gdk.Cursor(gtk.gdk.XTERM)

        self.connect('size-allocate', self._on_allocate)
        self.connect('button-press-event', self._on_press)
        #self.connect('enter-notify-event', self._on_enter)
        #self.connect('leave-notify-event', self._on_leave)
        #self.connect('button-release-event', self._on_release)
        self.connect('key-press-event', self._on_key_press)
        self.connect('motion-notify-event', self._on_motion)
        self.connect('style-set', self._on_style_set)
        return

    def _on_style_set(self, widget, old_style):
        self._bg_norm = self.style.base[gtk.STATE_NORMAL]
        self._fg_norm = self.style.text[gtk.STATE_NORMAL]
        self._bg_sel = self.style.base[gtk.STATE_SELECTED]
        self._fg_sel = self.style.text[gtk.STATE_SELECTED]
        self._grey = self.style.mid[gtk.STATE_NORMAL]
        return

    def _on_enter(self, widget, event):
        self.window.set_cursor(self._xterm)

    def _on_leave(self, widget, event):
        self.window.set_cursor(None)

    def _on_motion(self, widget, event):
        if not (event.state & gtk.gdk.BUTTON1_MASK): return
        self.selection.state = SelectionCursor.SELECT_NORMAL
        for layout in self.order:
            index = layout.index_at(int(event.x), int(event.y))
            if index:
                self.selection.set_position(layout.order_id, index)
                self.queue_draw()
                break

    def _on_press(self, widget, event):
        self.grab_focus()
        if event.button != 1: return

        for layout in self.order:
            index = layout.index_at(int(event.x), int(event.y))
            if index:
                self.cursor.set_position(layout.order_id, index)
                self.selection.clear()

                if (event.type == gtk.gdk._2BUTTON_PRESS):
                    self._2click_select(self.cursor, self.selection)
                elif (event.type == gtk.gdk._3BUTTON_PRESS):
                    self._3click_select(self.cursor, self.selection)
                self.queue_draw()
                break
        return

    def _on_release(self, widget, event):
        return

    def _on_key_press(self, widget, event):
        kv = event.keyval
        sel = self.selection

        handled_keys = True
        shift = event.state & gtk.gdk.SHIFT_MASK

        if shift:
            mover = self.selection
        else:
            mover = self.cursor
        s, i = mover.section, mover.index

        if kv == keys.Tab:
            handled_keys = False

        elif kv == keys.Left:
            if sel and not shift:
                self.cursor.set_position(*sel.min)
            elif i > 0:
                mover.set_position(s, i-1)
            elif s > 0:
                mover.section -= 1
                mover.set_position(s-1, len(self._get_layout(mover)))

        elif kv == keys.Right: 
            if sel and not shift:
                self.cursor.set_position(*sel.max)
            elif i < len(self._get_layout(mover)):
                mover.set_position(s, i+1)
            elif s < len(self.order)-1:
                mover.set_position(s+1, 0)

        elif kv == keys.Up:

            if sel and not shift:
                self.cursor.set_position(*sel.min)
            else:
                self._key_up(sel, self.cursor, self.cursor.section)

        elif kv == keys.Down:
            if self.selection and not shift:
                self.cursor.set_position(*sel.max)
            else:
                self._key_down(sel, self.cursor, self.cursor.section)

        elif kv == keys.Home:
            if shift:
                self._home_select(self.selection.state, self.order[s], i)
            else:
                self.cursor.set_position(0, 0)

        elif kv == keys.End:
            if shift:
                self._end_select(self.selection.state, self.order[s], i)
            else:
                self.cursor.section = len(self.order)-1
                self.cursor.index = len(self._get_layout(self.cursor))

        else:
            handled_keys = False

        if not shift and handled_keys:
            self.selection.clear()

        self.queue_draw()
        return handled_keys

    def _key_up(self, sel, mover, s):
        layout = self._get_layout(mover)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            j, xy = layout.cursor_up(mover, x)
        else:
            j, xy = layout.cursor_up(mover)
            sel.set_target_x(xy[0], layout.indent)

        if (s, j) != mover.get_position():
            mover.set_position(s, j)
        else:
            if s > 0:
                mover.section -= 1
            else:
                return False

            layout1 = self._get_layout(mover)
            x = sel.target_x + (sel.target_x_indent - layout1.indent)*PS
            y = layout1.get_extents()[1][3]
            j = sum(layout1.xy_to_index(x, y))
            mover.set_position(s-1, j)
        return True

    def _key_down(self, sel, mover, s):
        layout = self._get_layout(mover)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            j, xy = layout.cursor_down(mover, x)
        else:
            j, xy = layout.cursor_down(mover)
            sel.set_target_x(xy[0], layout.indent)

        if (s, j) != mover.get_position():
            mover.set_position(s, j)
        else:
            if s+1 < len(self.order):
                mover.section += 1
            else:
                return False

            layout = self._get_layout(mover)
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            j = sum(layout.xy_to_index(x, 0))
            mover.set_position(s+1, j)
        return True

    def _home_select(self, mode, layout, index):
        n, _range, line = self.cursor.get_current_line()

        if mode == SelectionCursor.SELECT_NORMAL or mode == SelectionCursor.SELECT_ALL:
            self.selection.state = SelectionCursor.SELECT_LINE
            self.selection.set_position(n[0], _range[0])

        elif mode == SelectionCursor.SELECT_LINE and n[1] != 0:
            if len(self.order) > 1 and layout.order_id != 0:
                self.selection.state = SelectionCursor.SELECT_PARA
            else:
                self.selection.state = SelectionCursor.SELECT_ALL
            self.selection.set_position(layout.order_id, 0)

        elif mode == SelectionCursor.SELECT_PARA or n[1] == 0:
            self.selection.state = SelectionCursor.SELECT_ALL
            self.selection.set_position(0, 0)
        self.queue_draw()

    def _end_select(self, mode, layout, index):
        n, _range, line = self.cursor.get_current_line()

        if mode == SelectionCursor.SELECT_NORMAL or mode == SelectionCursor.SELECT_ALL:
            self.selection.state = SelectionCursor.SELECT_LINE
            self.selection.set_position(n[0], _range[1])

        elif mode == SelectionCursor.SELECT_LINE and n[1] != layout.get_line_count()-1:
            if len(self.order) > 1 and layout.order_id != len(self.order)-1:
                self.selection.state = SelectionCursor.SELECT_PARA
            else:
                self.selection.state = SelectionCursor.SELECT_ALL
            self.selection.set_position(layout.order_id, len(layout))

        elif mode == SelectionCursor.SELECT_PARA or n[1] == layout.get_line_count()-1:
            self.selection.state = SelectionCursor.SELECT_ALL
            layout = self.order[-1]
            self.selection.set_position(layout.order_id, len(layout))
        self.queue_draw()

    def _2click_select(self, cursor, sel):
        self._select_word(cursor, sel)
        return

    def _3click_select(self, cursor, sel):
        self._select_line(cursor, sel)
        return

    def _select_word(self, cursor, sel):
        section, word = cursor.get_current_word()
        if word:
            cursor.set_position(section, word[0])
            sel.set_position(section, word[1])
            sel.state = SelectionCursor.SELECT_WORD
        return

    def _select_line(self, cursor, sel):
        n, _range, line = self.cursor.get_current_line()
        sel.state = SelectionCursor.SELECT_LINE
        cursor.index = _range[0]
        sel.index = _range[1]
        sel.order_id = n[0]
        return

    def _select_para(self, cursor, sel):
        if len(self.order) > 1:
            sel.state = SelectionCursor.SELECT_PARA
        else:
            sel.state = SelectionCursor.SELECT_ALL

        cursor.index = 0
        sel.index = len(layout)
        sel.order_id = layout.order_id
        return

    def _select_all(self, cursor, sel):
        self.selection.state = SelectionCursor.SELECT_ALL
        layout = self.order[-1]
        cursor.index = 0
        cursor.section = 0
        sel.index = len(layout)
        sel.section = layout.order_id
        return

    def height_from_width(self, width):
        if not self.order: return
        height = 0
        for layout in self.order:
            layout.set_width(PS*(width-layout.indent))
            height += layout.get_pixel_extents()[1][3] + self.line_height
        return width, height - self.line_height

    def _on_allocate(self, widget, a):
        if not self.order: return
        x = a.x
        y = a.y
        width = a.width
        for layout in self.order:
            lx,ly,lw,lh = layout.get_pixel_extents()[1]
            layout.set_allocation(x+lx+layout.indent, y+ly,
                                  width-layout.indent, lh)

            y += ly + lh + self.line_height
        return

    def _new_layout(self):
        layout = Layout(self, '')
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_markup(self.BULLET_POINT)
        return layout

    def _highlight_selection(self, i, start, end, layout, colours):
        if i == start[0]:
            if end[0] > i:
                layout.highlight(start[1], len(layout), colours)
            else:
                layout.highlight(start[1], end[1], colours)

        elif i == end[0]:
            if start[0] < i:
                layout.highlight(0, end[1], colours)
            else:
                layout.highlight(start[1], end[1], colours)

        else:
            layout.highlight_all(colours)
        return

    def draw(self, widget, event):
        if not self.order: return

        start, end = self.selection.get_range()
        cr = widget.window.cairo_create()
        if self.has_focus():
            bg_sel = self._bg_sel
            fg_sel = self._fg_sel
        else:
            bg_sel = self._grey
            fg_sel = self._fg_norm

        colours = (self._fg_norm, self._bg_norm,
                   fg_sel, bg_sel)

        for layout in self.order:
            la = layout.allocation
            i = layout.order_id

            if self.selection and i >= start[0] and i <= end[0]:
                self._highlight_selection(i, start, end, layout, colours)
            elif not layout._default_attrs:
                layout.reset_attrs(*colours[:2])

            if layout.is_bullet:
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
#        if self.has_focus():
#            self.cursor.draw(cr, self._get_layout(self.cursor), self.allocation)
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

    def _get_layout(self, cursor):
        return self.order[cursor.section]

    def _get_cursor_layout(self):
        return self.order[self.cursor.section]

    def _get_selection_layout(self):
        return self.order[self.selection.section]

    def append_paragraph(self, p):
        l = self._new_layout()
        l.order_id = len(self.order)

        l.set_text(p)
        self.order.append(l)
        return

    def append_bullet(self, point):
        l = self._new_layout()
        l.order_id = len(self.order)
        l.indent = self.indent
        l.is_bullet = True

        l.set_text(point)
        self.order.append(l)
        return

    def clear(self):
        self.cursor.zero()
        self.selection.clear()
        self.order = []
        return
