# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk, Gdk
from gi.repository import GObject
from gi.repository import Pango

from softwarecenter.utils import normalize_package_description

_PS = Pango.SCALE


def point_in(rect, px, py):
    return (px >= rect.x and px <= rect.x + rect.width and
            py >= rect.y and py <= rect.y + rect.height)

def color_floats(color):
    return color.red/65535.0, color.green/65535.0, color.blue/65535.0


class _SpecialCasePreParsers(object):

    def preparse(self, k, desc):
        if k is None:
            return desc
        func_name = '_%s_preparser' % k.lower()
        if not hasattr(self, func_name):
            return desc
        f = getattr(self, func_name)
        return f(desc)

    # special case pre-parsers
    def _skype_preparser(self, desc):
        return desc.replace('. *', '.\n*')


class EventHelper(dict):

    VALID_KEYS = (
        'event',
        'layout',
        'index',
        'within-selection',
        'drag-active',
        'drag-context')

    def __init__(self):
        dict.__init__(self)
        self.new_press(None, None, None, False)
        return

    def __setitem__(self, k, v):
        if k not in EventHelper.VALID_KEYS:
            raise KeyError('\"%s\" is not a valid key' % k)
            return False
        return dict.__setitem__(self, k, v)

    def new_press(self, event, layout, index, within_sel):
        self['event'] = event
        self['layout'] = layout
        self['index'] = index
        self['within-selection'] = within_sel
        self['drag-active'] = False
        self['drag-context'] = None
        return


class PangoLayoutProxy(object):

    """ Because i couldn't figure out how to inherit from
        pygi's Pango.Layout... """

    def __init__(self, context):
        self._layout = Pango.Layout.new(context)
        return

    def xy_to_index(self, x, y):
        return self._layout.xy_to_index(x, y)

    # setter proxies
    def set_attributes(self, attrs):
        return self._layout.set_attributes(attrs)
    
    def set_markup(self, markup):
        return self._layout.set_markup(markup, -1)

    def set_font_description(self, font_desc):
        return self._layout.set_font_description(font_desc)

    def set_wrap(self, wrap_mode):
        return self._layout.set_wrap(wrap_mode)

    def set_width(self, width):
        return self._layout.set_width(width)

    # getter proxies
    def get_text(self):
        return self._layout.get_text()

    def get_pixel_extents(self):
        return self._layout.get_pixel_extents()[1]

    def get_cursor_pos(self, index):
        return self._layout.get_cursor_pos(index)

    def get_iter(self):
        return self._layout.get_iter()


class Layout(PangoLayoutProxy):

    def __init__(self, widget, text=""):
        PangoLayoutProxy.__init__(self, widget.get_pango_context())

        self.widget = widget
        self.length = 0
        self.indent = 0
        self.vspacing = None
        self.is_bullet = False
        self.index = 0
        self.allocation = Gdk.Rectangle()
        self._default_attrs = True
        self.set_markup(text)
        return

    def __len__(self):
        return self.length

    def set_text(self, text):
        PangoLayoutProxy.set_markup(self, text)
        self.length = len(self.get_text())

    def set_allocation(self, x, y, w, h):
        a = self.allocation
        a.x = x
        a.y = y
        a.width = w
        a.height = h
        return

    def get_position(self):
        return self.allocation.x, self.allocation.y

    def cursor_up(self, cursor, target_x=-1):
        layout = self.widget.order[cursor.paragraph]
        x, y = layout.index_to_pos(cursor.index)[:2]

        if target_x >= 0:
            x = target_x

        y -= _PS*self.widget.line_height
        return sum(layout.xy_to_index(x, y)), (x, y)

    def cursor_down(self, cursor, target_x=-1):
        layout = self.widget.order[cursor.paragraph]
        x, y = layout.index_to_pos(cursor.index)[:2]

        if target_x >= 0:
            x = target_x

        y += _PS*self.widget.line_height
        return sum(layout.xy_to_index(x, y)), (x, y)

    def index_at(self, px, py):
        #wa = self.widget.get_allocation()
        x, y = self.get_position() # layout allocation
        return point_in(self.allocation, px, py), sum(self.xy_to_index((px-x)*_PS, (py-y)*_PS))

    def reset_attrs(self):
        self.set_attributes(Pango.AttrList())
        self._default_attrs = True
        return

    def highlight(self, start, end, bg, fg):
        # FIXME: AttrBackground doesnt seem to be expose by gi yet??
        #~ attrs = Pango.AttrList()
        #~ attrs.insert(Pango.AttrBackground(bg.red, bg.green, bg.blue, start, end))
        #~ attrs.insert(Pango.AttrForeground(fg.red, fg.green, fg.blue, start, end))
        #~ self.set_attributes(attrs)
        self._default_attrs = False
        return

    def highlight_all(self, bg, fg):
        # FIXME: AttrBackground doesnt seem to be expose by gi yet??
        #~ attrs = Pango.AttrList()
        #~ attrs.insert(Pango.AttrBackground(bg.red, bg.green, bg.blue, 0, -1))
        #~ attrs.insert(Pango.AttrForeground(fg.red, fg.green, fg.blue, 0, -1))
        #~ self.set_attributes(attrs)
        self._default_attrs = False
        return


class Cursor(object):

    WORD_TERMINATORS = (' ',)   # empty space. suggestions recommended...

    def __init__(self, parent):
        self.parent = parent
        self.index = 0
        self.paragraph = 0

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
        i, it = self.index, self.parent.order[self.paragraph].get_iter()
        ln = 0 
        while keep_going:
            l = it.get_line()
            ls = l.start_index
            le = ls + l.length

            if i >= ls and i <= le:
                if not it.at_last_line():
                    le -= 1
                return (self.paragraph, ln), (ls, le), l
            ln += 1
            keep_going = it.next_line()
        return None, None, None

    def get_current_word(self):
        keep_going = True
        layout = self.parent.order[self.paragraph]
        text = layout.get_text()
        i, it = self.index, layout.get_iter()
        start = 0
        while keep_going:
            j = it.get_index()
            if j >= i and text[j] in self.WORD_TERMINATORS:
                return self.paragraph, (start, j)

            elif text[j] in self.WORD_TERMINATORS:
                start = j+1

            keep_going = it.next_char()
        return self.paragraph, (start, len(layout))

    def set_position(self, paragraph, index):
        self.index = index
        self.paragraph = paragraph

    def get_position(self):
        return self.paragraph, self.index


class PrimaryCursor(Cursor):

    def __init__(self, parent):
        Cursor.__init__(self, parent)

    def __repr__(self):
        return 'Cursor: '+str((self.paragraph, self.index))

    def get_rectangle(self, layout, a):
        if self.index < len(layout):
            pos = layout.get_cursor_pos(self.index)[1]
        else:
            pos = layout.get_cursor_pos(len(layout))[1]

        x = layout.allocation.x + pos.x/_PS
        y = layout.allocation.y + pos.y/_PS
        return x, y, 1, pos.height/_PS

    def draw(self, cr, layout, a):
        cr.set_source_rgb(0,0,0)
        cr.rectangle(*self.get_rectangle(layout, a))
        cr.fill()
        return

    def zero(self):
        self.index = 0
        self.paragraph = 0


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
        return (self.paragraph, self.index) != (c.paragraph, c.index)

    @property
    def min(self):
        c = self.cursor
        return min((self.paragraph, self.index), (c.paragraph, c.index))

    @property
    def max(self):
        c = self.cursor
        return max((self.paragraph, self.index), (c.paragraph, c.index))

    def clear(self, key=None):
        self.index = self.cursor.index
        self.paragraph = self.cursor.paragraph
        self.restore_point = None

        if key not in (Gdk.KEY_uparrow, Gdk.KEY_downarrow):
            self.target_x = None
            self.target_x_indent = 0

    def set_target_x(self, x, indent):
        self.target_x = x
        self.target_x_indent = indent
        return

    def get_range(self):
        return self.min, self.max

    def within_selection(self, pos):
        l = list(self.get_range())
        l.append(pos)
        l.sort()
        # sort the list, see if pos is in between the extents of the selection
        # range, if it is, pos is within the selection
        if pos in l:
            return l.index(pos) == 1
        return False


class TextBlock(Gtk.EventBox):

    PAINT_PRIMARY_CURSOR = True
    DEBUG_PAINT_BBOXES = False

    BULLET_POINT = u' \u2022  '

    INFOCUS_NORM = 0
    INFOCUS_SEL  = 1
    OUTFOCUS_SEL = 2

    def __init__(self):
        Gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_size_request(200, -1)
        #~ self.set_redraw_on_allocate(False)

        self.set_can_focus(True)
        self.set_events(Gdk.EventMask.KEY_PRESS_MASK|
                        Gdk.EventMask.ENTER_NOTIFY_MASK|
                        Gdk.EventMask.LEAVE_NOTIFY_MASK|
                        Gdk.EventMask.BUTTON_RELEASE_MASK|
                        Gdk.EventMask.POINTER_MOTION_MASK)

        self._is_new = False
        self._bullet = self._new_layout()
        self._bullet.set_markup(self.BULLET_POINT)
        font_desc = Pango.FontDescription()

        font_desc.set_weight(Pango.Weight.BOLD)
        self._bullet.set_font_description(font_desc)

        event_helper = EventHelper()

        e = self._bullet.get_pixel_extents()
        self.indent, self.line_height  = e.width, e.height

        self.order = []
        self.cursor = cur = PrimaryCursor(self)
        self.selection = sel = SelectionCursor(self.cursor)
        self.clipboard = None

        self._test_layout = self.create_pango_layout('')
        #self._xterm = Gdk.Cursor.new(Gdk.XTERM)

        self.connect('button-press-event', self._on_press, event_helper, cur, sel)
        self.connect('button-release-event', self._on_release, event_helper, cur, sel)
        self.connect('motion-notify-event', self._on_motion, event_helper, cur, sel)

        self.connect('key-press-event', self._on_key_press, cur, sel)
        self.connect('key-release-event', self._on_key_release, cur, sel)

#        self.connect('drag-begin', self._on_drag_begin)
        #~ self.connect('drag-data-get', self._on_drag_data_get, sel)

        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)

        self.connect('style-updated', self._on_style_updated)
        return

    def do_size_allocate(self, allocation):
        width = allocation.width

        x = y = 0
        for layout in self.order:
            layout.set_width(_PS*(width-layout.indent))
            if layout.index > 0:
                y += (layout.vspacing or self.line_height)

            e = layout.get_pixel_extents()
            if self.get_direction() != Gtk.TextDirection.RTL:
                layout.set_allocation(e.x+layout.indent, y+e.y,
                                      width-layout.indent, e.height)
            else:
                layout.set_allocation(x+width-e.x-e.width-layout.indent-1, y+e.y,
                                      width-layout.indent, e.height)

            y += e.y + e.height

        self.set_allocation(allocation)
        return

    # overrides
    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_get_preferred_height_for_width(self, width):
        height = 0
        layout = self._test_layout
        for l in self.order:
            layout.set_text(l.get_text(), -1)
            layout.set_width(_PS*(width-l.indent))
            lh = layout.get_pixel_extents()[1].height
            height += lh + (l.vspacing or self.line_height)

        height = min(1000, max(50, height)) + 5
        return height, height

    def do_draw(self, cr):
        self.render(self, cr)
        return
     
    # small helper to be consitent with the ever changing pygi API
    def _color_parse(self, s):
        l = Gdk.color_parse(s)
        if type(l) is tuple:
            return l[1]
        return l

    def _on_style_updated(self, widget):
        #style = self.get_style()
        if self.has_focus():
            self._bg = self._color_parse('red')
            self._fg = self._color_parse('#000')
        else:
            #~ _, self._bg = Gdk.color_parse('#E5E3E1')
            self._bg = self._color_parse('red')
            self._fg = self._color_parse('#000')
        return

#    def _on_drag_begin(self, widgets, context, event_helper):
#        print 'drag: begin'
#        return

    def _on_drag_data_get(self, widget, context, selection, info, timestamp, sel):
#        print 'drag: get data'
        text = self.get_selected_text(sel)
        selection.set_text(text, -1)
        return

    def _on_focus_in(self, widget, event):
        #~ _, self._bg = self.style.base[Gtk.StateType.SELECTED]
        self._bg = self._color_parse('red')
        self._fg = self._color_parse('#000')
        return

    def _on_focus_out(self, widget, event):
        #~ _, self._bg = Gdk.color_parse('#E5E3E1')
        self._bg = self._color_parse('red')
        self._fg = self._color_parse('#000')
        return

    def _on_motion(self, widget, event, event_helper, cur, sel):

        state = event.get_state().value_nicks

        if not (state and state[0] == 'button1_mask'):# or not self.has_focus():
            return

        # check if we have moved enough to count as a drag
        press = event_helper['event']
        # mvo: how can this be?
        if not press: return

        start_x, start_y = int(press.x), int(press.y)
        cur_x, cur_y = int(event.x), int(event.y)

        if (not event_helper['drag-active'] and
            self.drag_check_threshold(start_x, start_y, cur_x, cur_y)):
            event_helper['drag-active'] = True

            # FIXME
        #~ if not event_helper['drag-active']: 
            #~ return
#~ 
        #~ if (event_helper['within-selection'] and 
            #~ not event_helper['drag-context']):
            #~ target_list = Gtk.TargetList()
            #~ target_list.add_text_targets(80)
            #~ ctx = self.drag_begin(target_list,              # target list
                                  #~ Gdk.DragAction.COPY,      # action
                                  #~ 1,                        # initiating button
                                  #~ event)                    # event
#~ 
            #~ event_helper['drag-context'] = ctx
            return

        for layout in self.order:
            point_in, index = layout.index_at(int(event.x), int(event.y))
            if point_in:
                cur.set_position(layout.index, index)
                self.queue_draw()
                break

    def _on_press(self, widget, event, event_helper, cur, sel):

        #~ if sel and not self.has_focus():
            #~ self.grab_focus()
            #~ return  # spot the difference
#~ 
        #~ if not self.has_focus():
            #~ self.grab_focus()

        if event.button == 3:
            self._button3_action(cur, sel, event)
            return

        elif event.button != 1:
            return

        for layout in self.order:
            x, y = int(event.x), int(event.y)
            point_in, index = layout.index_at(x, y)

            if point_in:
                within_sel = sel.within_selection((layout.index, index))

                if not within_sel:
                    cur.set_position(layout.index, index)
                    sel.clear()

                event_helper.new_press(event.copy(), layout, index, within_sel)
                break
        return

    def _on_release(self, widget, event, event_helper, cur, sel):
        if not event_helper['event']: return

        # check if a drag occurred
        if event_helper['drag-active']:
            # if so, do not handle release
            return

        # else, handle release, do click
        cur.set_position(event_helper['layout'].index,
                         event_helper['index'])
        sel.clear()

        press = event_helper['event']

        if (press.type == Gdk.EventType._2BUTTON_PRESS):
            self._2click_select(cur, sel)
        elif (press.type == Gdk.EventType._3BUTTON_PRESS):
            self._3click_select(cur, sel)

        self.queue_draw()
        return

    def _menu_do_copy(self, item, sel):
        self._copy_text(sel)

    def _menu_do_select_all(self, item, cur, sel):
        self._select_all(cur, sel)

    def _button3_action(self, cur, sel, event):
        copy = Gtk.ImageMenuItem(stock_id=Gtk.STOCK_COPY, accel_group=None)
        sel_all = Gtk.ImageMenuItem(stock_id=Gtk.STOCK_SELECT_ALL, accel_group=None)

        menu = Gtk.Menu()
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

    def _on_key_press(self, widget, event, cur, sel):
        kv = event.keyval
        s, i = cur.paragraph, cur.index

        handled_keys = True
        state = event.get_state().value_nicks
        ctrl = state and state[0] == 'control_mask'
        shift = state and state[0] == 'shift_mask'

        if not self.PAINT_PRIMARY_CURSOR and \
            kv in (Gdk.KEY_uparrow, Gdk.KEY_downarrow) and not sel:
            return False

        if kv == Gdk.KEY_Tab:
            handled_keys = False

        elif kv == Gdk.KEY_Left:
            if ctrl:
                self._select_left_word(cur, sel, s, i)
            else:
                self._select_left(cur, sel, s, i, shift)

            if shift:
                layout = self._get_cursor_layout()
                sel.set_target_x(layout.index_to_pos(cur.index)[0], layout.indent)

        elif kv == Gdk.KEY_Right: 
            if ctrl:
                self._select_right_word(cur, sel, s, i)
            else:
                self._select_right(cur, sel, s, i, shift)

            if shift:
                layout = self._get_cursor_layout()
                sel.set_target_x(layout.index_to_pos(cur.index)[0], layout.indent)

        elif kv == Gdk.KEY_Up:
            if ctrl:
                if i == 0:
                    if s > 0:
                        cur.paragraph -= 1
                cur.set_position(cur.paragraph, 0)
            elif sel and not shift:
                cur.set_position(*sel.min)
            else:
                self._select_up(cur, sel)

        elif kv == Gdk.KEY_Down:
            if ctrl:
                if i == len(self._get_layout(cur)):
                    if s+1 < len(self.order):
                        cur.paragraph += 1
                i = len(self._get_layout(cur))
                cur.set_position(cur.paragraph, i)
            elif sel and not shift:
                cur.set_position(*sel.max)
            else:
                self._select_down(cur, sel)

        elif kv == Gdk.KEY_Home:
            if shift:
                self._select_home(cur, sel, self.order[cur.paragraph])
            else:
                cur.set_position(0, 0)

        elif kv == Gdk.KEY_End:
            if shift:
                self._select_end(cur, sel, self.order[cur.paragraph])
            else:
                cur.paragraph = len(self.order)-1
                cur.index = len(self._get_layout(cur))

        else:
            handled_keys = False

        if not shift and handled_keys:
            sel.clear(kv)

        self.queue_draw()
        return handled_keys

    def _on_key_release(self, widget, event, cur, sel):
        state = event.get_state().value_nicks
        ctrl = state and state[0] == 'control_mask'
        if ctrl:
            if event.keyval == Gdk.KEY_a:
                self._select_all(cur, sel)

            elif event.keyval == Gdk.KEY_c:
                self._copy_text(sel)

            self.queue_draw()
        return

    def _select_up(self, cur, sel):
        if sel and not cur.is_min(sel) and cur.same_line(sel):
            cur.switch(sel)
        s = cur.paragraph

        layout = self._get_layout(cur)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*_PS
            j, xy = layout.cursor_up(cur, x)
        else:
            j, xy = layout.cursor_up(cur)
            sel.set_target_x(xy[0], layout.indent)

        if (s, j) != cur.get_position():
            cur.set_position(s, j)
        else:
            if s > 0:
                cur.paragraph -= 1
            else:
                cur.set_position(0, 0)
                return False

            layout1 = self._get_layout(cur)
            x = sel.target_x + (sel.target_x_indent - layout1.indent)*_PS
            y = layout1.get_extents()[1][3]
            j = sum(layout1.xy_to_index(x, y))
            cur.set_position(s-1, j)
        return

    def _select_down(self, cur, sel):
        if sel and not cur.is_max(sel) and cur.same_line(sel):
            cur.switch(sel)
        s = cur.paragraph

        layout = self._get_layout(cur)

        if sel.target_x:
            x = sel.target_x + (sel.target_x_indent - layout.indent)*_PS
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
                cur.paragraph += 1
            else:
                cur.set_position(s, len(layout))
                return False

            layout = self._get_layout(cur)
            x = sel.target_x + (sel.target_x_indent - layout.indent)*_PS
            j = sum(layout.xy_to_index(x, 0))
            cur.set_position(s+1, j)
        return True

    def _2click_select(self, cursor, sel):
        self._select_word(cursor, sel)
        return

    def _3click_select(self, cursor, sel):
        #~ self._select_line(cursor, sel)
        return

    def _copy_text(self, sel):

        text = self.get_selected_text(sel)

        if not self.clipboard:
            self.clipboard = self.get_clipboard(Gdk.SELECTION_CLIPBOARD)

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

        elif cur_pos == (n[0], r[0]):      # line home
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
        elif cur.paragraph > 0:
            cur.paragraph -= 1
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
            cur.paragraph -= 1
            cur.index = len(self._get_layout(cur))

        paragraph, word = cur.get_current_word()
        if not word: return
        cur.set_position(paragraph, max(0, word[0]-1))
        return

    def _select_right_word(self, cur, sel, s, i):
        ll = len(self._get_layout(cur))
        if i < ll:
            cur.index += 1
        elif s+1 < len(self.order):
            cur.paragraph += 1
            cur.index = 0

        paragraph, word = cur.get_current_word()
        if not word: return
        cur.set_position(paragraph, min(word[1]+1, ll))
        return

    def _select_word(self, cursor, sel):
        paragraph, word = cursor.get_current_word()
        if word:
            cursor.set_position(paragraph, word[1]+1)
            sel.set_position(paragraph, word[0])
            if self.get_direction() == Gtk.TextDirection.RTL:
                cursor.switch(sel)
        return

    def _select_line(self, cursor, sel):
        n, r, line = self.cursor.get_current_line()
        sel.set_position(n[0], r[0])
        cursor.set_position(n[0], r[1])
        if self.get_direction() == Gtk.TextDirection.RTL:
            cursor.switch(sel)
        return

    def _select_all(self, cursor, sel):
        layout = self.order[-1]
        sel.set_position(0, 0)
        cursor.set_position(layout.index, len(layout))
        if self.get_direction() == Gtk.TextDirection.RTL:
            cursor.switch(sel)
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

    def _new_layout(self, text=''):
        layout = Layout(self, text)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
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

    def _paint_bullet_point(self, cr, x, y):
        # draw the layout
        Gtk.render_layout(self.get_style_context(),
                            cr,             # state
                            x,           # x coord
                            y,           # y coord
                            self._bullet._layout)   # a Pango.Layout()

    def _get_layout(self, cursor):
        return self.order[cursor.paragraph]

    def _get_cursor_layout(self):
        return self.order[self.cursor.paragraph]

    def _get_selection_layout(self):
        return self.order[self.selection.paragraph]

    def render(self, widget, cr):
        if not self.order: 
            return

        a = self.get_allocation()
        for layout in self.order:
            lx, ly = layout.get_position()
#~ 
            #~ self._selection_highlight(layout,
                                      #~ self.selection,
                                      #~ self._bg, self._fg)

            if layout.is_bullet:
                if self.get_direction() != Gtk.TextDirection.RTL:
                    indent = layout.indent - self.indent
                    self._paint_bullet_point(cr, indent, ly)
                else:
                    self._paint_bullet_point(cr, a.width-indent, ly)

            if self.DEBUG_PAINT_BBOXES:
                la = layout.allocation
                cr.rectangle(la.x, la.y, la.width, la.height)
                cr.set_source_rgb(1,0,0)
                cr.stroke()

            #~ # draw the layout
            Gtk.render_layout(self.get_style_context(),
                                cr,
                                lx,             # x coord
                                ly,             # y coord
                                layout._layout)           # a Pango.Layout()

        # draw the cursor
        if self.PAINT_PRIMARY_CURSOR and self.has_focus():
            self.cursor.draw(cr, self._get_layout(self.cursor), a)
        return

    def append_paragraph(self, p, vspacing=None):
        l = self._new_layout()
        l.index = len(self.order)
        l.vspacing = vspacing
        l.set_text(p)
        self.order.append(l)
        return

    def append_bullet(self, point, indent_level, vspacing=None):
        l = self._new_layout()
        l.index = len(self.order)
        l.indent = self.indent * (indent_level + 1)
        l.vspacing = vspacing
        l.is_bullet = True

        l.set_text(point)
        self.order.append(l)
        return

    def copy_clipboard(self):
        self._copy_text(self.selection)
        return

    def get_selected_text(self, sel=None):
        text = ''
        if not sel:
            sel = self.selection
        for layout in self.order:
            text += self._selection_copy(layout, sel, (layout.index > 0))
        return text

    def select_all(self):
        self._select_all(self.cursor, self.selection)
        self.queue_draw()
        return

    def finished(self):
        self.queue_resize()
        return

    def clear(self, key=None):
        self.cursor.zero()
        self.selection.clear(key)
        self.order = []
        return


class AppDescription(Gtk.VBox):

    TYPE_PARAGRAPH = 0
    TYPE_BULLET    = 1

    _preparser = _SpecialCasePreParsers()

    def __init__(self):
        Gtk.VBox.__init__(self)
        self.description = TextBlock()
        self.pack_start(self.description, False, False, 0)
        self._prev_type = None
        return

    def _part_is_bullet(self, part):
        # normalize_description() ensures that we only have "* " bullets
        i = part.find("* ")
        return i > -1, i

    def _parse_desc(self, desc, pkgname):
        """ Attempt to maintain original fixed width layout, while 
            reconstructing the description into text blocks 
            (either paragraphs or bullets) which are line-wrap friendly.
        """
        # pre-parse descrition if special case exists for the given pkgname
        desc = self._preparser.preparse(pkgname, desc)

        parts = normalize_package_description(desc).split('\n')
        for part in parts:
            if not part: continue
            is_bullet, indent = self._part_is_bullet(part)
            if is_bullet:
                self.append_bullet(part, indent)
            else:
                self.append_paragraph(part)

        self.description.finished()
        return

    def clear(self):
        self.description.clear()
        return

    def append_paragraph(self, p):
        vspacing = self.description.line_height
        self.description.append_paragraph(p.strip(), vspacing)
        self._prev_type = self.TYPE_PARAGRAPH
        return

    def append_bullet(self, point, indent_level):
        if self._prev_type == self.TYPE_BULLET:
            vspacing = int(0.4*self.description.line_height)
        else:
            vspacing = self.description.line_height

        self.description.append_bullet(
                        point[indent_level+2:], indent_level, vspacing)
        self._prev_type = self.TYPE_BULLET
        return

    def set_description(self, raw_desc, pkgname):
        self.clear()
        if type(raw_desc) == str:
            encoded_desc = unicode(raw_desc, 'utf8').encode('utf8')
        else:
            encoded_desc = raw_desc.encode('utf8')
        desc = GObject.markup_escape_text(encoded_desc)
        self._parse_desc(desc, pkgname)
        self.show_all()
        return

    # easy access to some TextBlock methods
    def copy_clipboard(self):
        return TextBlock.copy_clipboard(self.description)

    def get_selected_text(self):
        return TextBlock.get_selected_text(self.description)

    def select_all(self):
        return TextBlock.select_all(self.description)


def get_test_description_window():
    EXAMPLE = """
p7zip is the Unix port of 7-Zip, a file archiver that archives with very high compression ratios.

p7zip-full provides:

 - /usr/bin/7za a standalone version of the 7-zip tool that handles 
   7z archives (implementation of the LZMA compression algorithm) and some other formats.

 - /usr/bin/7z not only does it handle 7z but also ZIP, Zip64, CAB, RAR, ARJ, GZIP, 
   BZIP2, TAR, CPIO, RPM, ISO and DEB archives. 7z compression is 30-50% better than ZIP compression.

p7zip provides 7zr, a light version of 7za, and p7zip a gzip like wrapper around 7zr.""".strip()
    win = Gtk.Window()
    win.set_size_request(400, -1)
    win.set_has_resize_grip(True)
    d = AppDescription()
    d.set_description(EXAMPLE, pkgname='')
    win.add(d)
    win.connect('destroy',lambda x: Gtk.main_quit())
    return win

if __name__ == '__main__':
    win = get_test_description_window()
    win.show_all()
    Gtk.main()

