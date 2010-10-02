import gtk
import pango
import gobject

from pango import SCALE as PS
from gtk import keysyms as keys

from gettext import gettext as _


class Layout(pango.Layout):

    def __init__(self, widget, text=''):
        pango.Layout.__init__(self, widget.get_pango_context())

        self.widget = widget
        self.length = 0
        self.indent = 0
        self.vspacing = None
        self.is_bullet = False
        self.index = 0
        self.allocation = gtk.gdk.Rectangle(0,0,1,1)
        self._default_attrs = True
        self.set_markup(text)
        return

    def __len__(self):
        return self.length

    def set_text(self, text):
        pango.Layout.set_markup(self, text)
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
        a = self.allocation # layout allocation
        return gtk.gdk.region_rectangle(a).point_in(px, py), sum(self.xy_to_index((px-a.x)*PS, (py-a.y)*PS))

    def reset_attrs(self):
        self.set_attributes(pango.AttrList())
        self._default_attrs = True
        return

    def highlight(self, start, end, bg, fg):
        attrs = pango.AttrList()
        attrs.insert(pango.AttrBackground(bg.red, bg.green, bg.blue, start, end))
        attrs.insert(pango.AttrForeground(fg.red, fg.green, fg.blue, start, end))
        self.set_attributes(attrs)
        self._default_attrs = False
        return

    def highlight_all(self, bg, fg):
        attrs = pango.AttrList()
        attrs.insert(pango.AttrBackground(bg.red, bg.green, bg.blue, 0, -1))
        attrs.insert(pango.AttrForeground(fg.red, fg.green, fg.blue, 0, -1))
        self.set_attributes(attrs)
        self._default_attrs = False
        return


class Cursor(object):

    WORD_TERMINATORS = (' ', ',', '.', ':', ';', '!', '?', '(', ')', '[', ']', '{', '}')

    def __init__(self, parent):
        self.parent = parent
        self.index = 0
        self.section = 0

    def is_min(self, cursor):
        return self.get_position() <= cursor.get_position()

    def is_max(self, cursor):
        return self.get_position() >= cursor.get_position()

    def switch(self, cursor):
        this_pos = self.get_position()
        other_pos = cursor.get_position()
        self.set_position(*other_pos)
        cursor.set_position(*this_pos)
        return

    def same_line(self, cursor):
        return self.get_current_line()[0] == cursor.get_current_line()[0]

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

    def set_position(self, section, index):
        self.index = index
        self.section = section

    def get_position(self):
        return self.section, self.index


class PrimaryCursor(Cursor):

    def __init__(self, parent):
        Cursor.__init__(self, parent)

    def __repr__(self):
        return 'Cursor: '+str((self.section, self.index))

    def get_rectangle(self, layout, a):
        if self.index < len(layout):
            x, y, w, h = layout.get_cursor_pos(self.index)[1]
        else:
            x, y, w, h = layout.get_cursor_pos(len(layout))[1]
        x = layout.allocation.x + x/PS
        y = layout.allocation.y + y/PS
        return x, y, 1, h/PS

    def draw(self, cr, layout, a):
        cr.set_source_rgb(0,0,0)
        cr.rectangle(*self.get_rectangle(layout, a))
        cr.fill()
        return

    def zero(self):
        self.index = 0
        self.section = 0


class SelectionCursor(Cursor):

    def __init__(self, cursor):
        Cursor.__init__(self, cursor.parent)
        self.cursor = cursor
        self.target_x = None
        self.target_x_indent = 0
        self.restore_point = None

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

    def clear(self, key=None):
        self.index = self.cursor.index
        self.section = self.cursor.section
        self.restore_point = None

        if key not in (keys.Up, keys.Down):
            self.target_x = None
            self.target_x_indent = 0

    def set_target_x(self, x, indent):
        self.target_x = x
        self.target_x_indent = indent
        return

    def get_range(self):
        return self.min, self.max

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


class IndentLabel(gtk.EventBox):

    PAINT_PRIMARY_CURSOR = True
    BULLET_POINT = u'  \u2022  '

    INFOCUS_NORM = 0
    INFOCUS_SEL  = 1
    OUTFOCUS_SEL = 2

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
        self.clipboard = None

        self._xterm = gtk.gdk.Cursor(gtk.gdk.XTERM)
        self._ppoller = 0

        # TODO: drag n drop
        #self.drag_source_set(gtk.gdk.BUTTON1_MASK, [("text/plain", 0, 80),], gtk.gdk.ACTION_COPY)

        self.connect('size-allocate', self._on_allocate)
        self.connect('button-press-event', self._on_press, self.cursor, self.selection)
        self.connect('key-press-event', self._on_key_press, self.cursor, self.selection)
        self.connect('key-release-event', self._on_key_release, self.cursor, self.selection)
        self.connect('motion-notify-event', self._on_motion, self.cursor, self.selection)

        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)

        self.connect('style-set', self._on_style_set)
        return

    def _on_style_set(self, widget, old_style):
        if self.has_focus():
            self._bg = self.style.base[gtk.STATE_SELECTED]
            self._fg = self.style.text[gtk.STATE_SELECTED]
        else:
            self._bg = gtk.gdk.color_parse('#E5E3E1')
            self._fg = self.style.text[gtk.STATE_NORMAL]
        return

    def _on_focus_in(self, widget, event):
        self._bg = self.style.base[gtk.STATE_SELECTED]
        self._fg = self.style.text[gtk.STATE_SELECTED]
        return

    def _on_focus_out(self, widget, event):
        self._bg = gtk.gdk.color_parse('#E5E3E1')
        self._fg = self.style.text[gtk.STATE_NORMAL]
        return

    def _on_motion(self, widget, event, cur, sel):
        if not (event.state & gtk.gdk.BUTTON1_MASK) or not self.has_focus(): return
        for layout in self.order:
            point_in, index = layout.index_at(int(event.x), int(event.y))
            if point_in:
                cur.set_position(layout.index, index)
                self.queue_draw()
                break

    def _on_press(self, widget, event, cur, sel):
        if sel and not self.has_focus():
            self.grab_focus()
            return
        elif not self.has_focus():
            self.grab_focus()

        if event.button == 3:
            self._button3_action(cur, sel, event)
            return
        elif event.button != 1:
            return

        for layout in self.order:
            point_in, index = layout.index_at(int(event.x), int(event.y))
            if point_in:
                cur.set_position(layout.index, index)
                sel.clear()

                if (event.type == gtk.gdk._2BUTTON_PRESS):
                    self._2click_select(cur, sel)
                elif (event.type == gtk.gdk._3BUTTON_PRESS):
                    self._3click_select(cur, sel)
                self.queue_draw()
                break
        return

    def _menu_do_copy(self, item, sel):
        self._copy_text(sel)

    def _menu_do_select_all(self, item, cur, sel):
        self._select_all(cur, sel)

    def _button3_action(self, cur, sel, event):
        copy = gtk.ImageMenuItem(stock_id=gtk.STOCK_COPY, accel_group=None)
        sel_all = gtk.ImageMenuItem(stock_id=gtk.STOCK_SELECT_ALL, accel_group=None)

        menu = gtk.Menu()
        menu.append(copy)
        menu.append(sel_all)
        menu.show_all()

        start, end = sel.get_range()
        if not sel:
            copy.set_sensitive(False)
        elif start == (0, 0) and \
            end == (len(self.order)-1, len(self.order[-1])):
            sel_all.set_sensitive(False)

        copy.connect('select', self._menu_do_copy, sel)
        sel_all.connect('select', self._menu_do_select_all, cur, sel)

        menu.popup(None, None, None,
                   event.button, event.time,
                   data=None)
        return

    def _on_release(self, widget, event):
        return

    def _on_key_press(self, widget, event, cur, sel):
        kv = event.keyval
        s, i = cur.section, cur.index

        handled_keys = True
        ctrl = event.state & gtk.gdk.CONTROL_MASK
        shift = event.state & gtk.gdk.SHIFT_MASK

        if kv == keys.Tab:
            handled_keys = False

        elif kv == keys.Left:
            if ctrl:
                self._select_left_word(cur, sel, s, i)
            else:
                self._select_left(cur, sel, s, i, shift)

            if shift:
                layout = self._get_cursor_layout()
                sel.set_target_x(layout.index_to_pos(cur.index)[0], layout.indent)

        elif kv == keys.Right: 
            if ctrl:
                self._select_right_word(cur, sel, s, i)
            else:
                self._select_right(cur, sel, s, i, shift)

            if shift:
                layout = self._get_cursor_layout()
                sel.set_target_x(layout.index_to_pos(cur.index)[0], layout.indent)

        elif kv == keys.Up:
            if ctrl:
                if i == 0:
                    if s > 0:
                        cur.section -= 1
                cur.set_position(cur.section, 0)
            elif sel and not shift:
                cur.set_position(*sel.min)
            else:
                self._select_up(cur, sel)

        elif kv == keys.Down:
            if ctrl:
                if i == len(self._get_layout(cur)):
                    if s+1 < len(self.order):
                        cur.section += 1
                i = len(self._get_layout(cur))
                cur.set_position(cur.section, i)
            elif sel and not shift:
                cur.set_position(*sel.max)
            else:
                self._select_down(cur, sel)

        elif kv == keys.Home:
            if shift:
                self._select_home(cur, sel, self.order[cur.section])
            else:
                cur.set_position(0, 0)

        elif kv == keys.End:
            if shift:
                self._select_end(cur, sel, self.order[cur.section])
            else:
                cur.section = len(self.order)-1
                cur.index = len(self._get_layout(cur))

        else:
            handled_keys = False

        if not shift and handled_keys:
            sel.clear(kv)

        self.queue_draw()
        return handled_keys

    def _on_key_release(self, widget, event, cur, sel):
        ctrl = event.state & gtk.gdk.CONTROL_MASK
        if ctrl:
            if event.keyval == keys.a:
                self._select_all(cur, sel)

            elif event.keyval == keys.c:
                self._copy_text(sel)

            self.queue_draw()
        return

    def _select_up(self, cur, sel):
        if sel and not cur.is_min(sel) and cur.same_line(sel):
            cur.switch(sel)
        s = cur.section

        layout = self._get_layout(cur)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            # special case for when we sel all of bottom line after 
            # hitting bottom line extent
            if cur.get_position() == (len(self.order)-1, len(layout)) and x != layout.get_extents()[1][2]:
                y = layout.get_extents()[1][3]
                j = sum(layout.xy_to_index(x, y))
                xy = (x,y)
            else:
                j, xy = layout.cursor_up(cur, x)
        else:
            j, xy = layout.cursor_up(cur)
            sel.set_target_x(xy[0], layout.indent)

        if (s, j) != cur.get_position():
            cur.set_position(s, j)
        else:
            if s > 0:
                cur.section -= 1
            else:
                cur.set_position(0, 0)
                return False

            layout1 = self._get_layout(cur)
            x = sel.target_x + (sel.target_x_indent - layout1.indent)*PS
            y = layout1.get_extents()[1][3]
            j = sum(layout1.xy_to_index(x, y))
            cur.set_position(s-1, j)
        return

    def _select_down(self, cur, sel):
        if sel and not cur.is_max(sel) and cur.same_line(sel):
            cur.switch(sel)
        s = cur.section

        layout = self._get_layout(cur)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            # special case for when we sel all of top line after hitting
            # top line extent
            if cur.get_position() == (0, 0) and x != 0:
                j = sum(layout.xy_to_index(x, 0))
                xy = (x,0)
            else:
                j, xy = layout.cursor_down(cur, x)
        else:
            j, xy = layout.cursor_down(cur)
            sel.set_target_x(xy[0], layout.indent)

        if (s, j) != cur.get_position():
            cur.set_position(s, j)
        else:
            if s+1 < len(self.order):
                cur.section += 1
            else:
                cur.set_position(s, len(layout))
                return False

            layout = self._get_layout(cur)
            x = sel.target_x + (sel.target_x_indent - layout.indent)*PS
            j = sum(layout.xy_to_index(x, 0))
            cur.set_position(s+1, j)
        return True

    def _2click_select(self, cursor, sel):
        self._select_word(cursor, sel)
        return

    def _3click_select(self, cursor, sel):
        self._select_line(cursor, sel)
        return

    def _copy_text(self, sel):
        text = ''
        for layout in self.order:
            text += self._selection_copy(layout, sel, (layout.index > 0))

        if not self.clipboard:
            self.clipboard = self.get_clipboard(gtk.gdk.SELECTION_CLIPBOARD)

        self.clipboard.clear()
        self.clipboard.set_text(text, -1)
        return

    def _select_end(self, cur, sel, layout):
        if not cur.is_max(sel):
            cur.switch(sel)

        n, r, line = cur.get_current_line()
        cur_pos = cur.get_position()

        if cur_pos == (len(self.order)-1, len(self.order[-1])):   # absolute end
            if sel.restore_point:
                # reinstate restore point
                cur.set_position(*sel.restore_point)
            else:
                # reselect the line end
                n, r, line = sel.get_current_line()
                cur.set_position(n[0], r[1])

        elif cur_pos[1] == len(self.order[n[0]]):   # para end
            # select abs end
            cur.set_position(len(self.order)-1, len(self.order[-1]))

        elif cur_pos == (n[0], r[1]):   # line end
            # select para end
            cur.set_position(n[0], len(self.order[n[0]]))

        else:   # not at any end, within line somewhere
            # select line end
            if sel:
                sel.restore_point = cur_pos
            cur.set_position(n[0], r[1])
        return

    def _select_home(self, cur, sel, layout):
        if not cur.is_min(sel):
            cur.switch(sel)

        n, r, line = cur.get_current_line()
        cur_pos = cur.get_position()

        if cur_pos == (0, 0):   # absolute home
            if sel.restore_point:
                cur.set_position(*sel.restore_point)
            else:
                n, r, line = sel.get_current_line()
                cur.set_position(n[0], r[0])

        elif cur_pos[1] == 0:   # para home
            cur.set_position(0,0)

        elif cur_pos == (n[0], r[1]):      # line home
            cur.set_position(n[0], 0)

        else:                   # not at any home, within line somewhere
            if sel:
                sel.restore_point = cur_pos
            cur.set_position(n[0], r[0])
        return

    def _select_left(self, cur, sel, s, i, shift):
        if not shift and not cur.is_min(sel):
            cur.switch(sel)
            return
        if i > 0:
            cur.set_position(s, i-1)
        elif cur.section > 0:
            cur.section -= 1
            cur.set_position(s-1, len(self._get_layout(cur)))
        return

    def _select_right(self, cur, sel, s, i, shift):
        if not shift and not cur.is_max(sel):
            cur.switch(sel)
            return
        if i < len(self._get_layout(cur)):
            cur.set_position(s, i+1)
        elif s < len(self.order)-1:
            cur.set_position(s+1, 0)
        return

    def _select_left_word(self, cur, sel, s, i):
        if i > 0:
            cur.index -= 1
        elif s > 0:
            cur.section -= 1
            cur.index = len(self._get_layout(cur))

        section, word = cur.get_current_word()
        if not word: return
        cur.set_position(section, max(0, word[0]-1))
        return

    def _select_right_word(self, cur, sel, s, i):
        ll = len(self._get_layout(cur))
        if i < ll:
            cur.index += 1
        elif s+1 < len(self.order):
            cur.section += 1
            cur.index = 0

        section, word = cur.get_current_word()
        if not word: return
        cur.set_position(section, min(word[1]+1, ll))
        return

    def _select_word(self, cursor, sel):
        section, word = cursor.get_current_word()
        if word:
            cursor.set_position(section, word[1]+1)
            sel.set_position(section, word[0])
        return

    def _select_line(self, cursor, sel):
        n, r, line = self.cursor.get_current_line()
        sel.set_position(n[0], r[0])
        cursor.set_position(n[0], r[1]-1)
        return

    def _select_all(self, cursor, sel):
        layout = self.order[-1]
        sel.set_position(0, 0)
        cursor.set_position(layout.index, len(layout))
        return

    def _selection_copy(self, layout, sel, new_para=True):
        i = layout.index
        start, end = sel.get_range()

        if new_para:
            text = '\n\n'
        else:
            text = ''

        if sel and i >= start[0] and i <= end[0]:

            if i == start[0]:
                if end[0] > i:
                    return text+layout.get_text()[start[1]: len(layout)]
                else:
                    return text+layout.get_text()[start[1]: end[1]]

            elif i == end[0]:
                if start[0] < i:
                    return text+layout.get_text()[0: end[1]]
                else:
                    return text+layout.get_text()[start[1]: end[1]]

            else:
                return text+layout.get_text()
        return ''

    def _on_allocate(self, widget, a):
        if not self.order: return
        x = a.x
        y = a.y
        width = a.width
        for layout in self.order:
            if layout.index > 0:
                y += (layout.vspacing or self.line_height)

            lx,ly,lw,lh = layout.get_pixel_extents()[1]
            layout.set_allocation(x+lx+layout.indent, y+ly,
                                  width-layout.indent, lh)

            y += ly + lh
        return

    def _new_layout(self, text=''):
        layout = Layout(self, text)
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        return layout

    def _selection_highlight(self, layout, sel, bg, fg):
        i = layout.index
        start, end = sel.get_range()
        if sel and i >= start[0] and i <= end[0]:

            if i == start[0]:
                if end[0] > i:
                    layout.highlight(start[1], len(layout), bg, fg)
                else:
                    layout.highlight(start[1], end[1], bg, fg)

            elif i == end[0]:
                if start[0] < i:
                    layout.highlight(0, end[1], bg, fg)
                else:
                    layout.highlight(start[1], end[1], bg, fg)

            else:
                layout.highlight_all(bg, fg)

        elif not layout._default_attrs:
            layout.reset_attrs()
        return

    def draw(self, widget, event):
        if not self.order: return

        cr = widget.window.cairo_create()

        for layout in self.order:
            la = layout.allocation

            self._selection_highlight(layout,
                                      self.selection,
                                      self._bg, self._fg)

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
        if self.PAINT_PRIMARY_CURSOR and self.has_focus():
            self.cursor.draw(cr, self._get_layout(self.cursor), self.allocation)
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

    def height_from_width(self, width):
        if not self.order: return
        height = 0
        for layout in self.order:
            layout.set_width(PS*(width-layout.indent))
            height += layout.get_pixel_extents()[1][3] + (layout.vspacing or self.line_height)

        return width, height - self.line_height

    def append_paragraph(self, p, vspacing=None):
        l = self._new_layout()
        l.index = len(self.order)
        l.vspacing = vspacing
        l.set_text(p)
        self.order.append(l)
        return

    def append_bullet(self, point, vspacing=None):
        l = self._new_layout()
        l.index = len(self.order)
        l.indent = self.indent
        l.vspacing = vspacing
        l.is_bullet = True

        l.set_text(point)
        self.order.append(l)
        return

    def clear(self, key=None):
        self.cursor.zero()
        self.selection.clear(key)
        self.order = []
        return
