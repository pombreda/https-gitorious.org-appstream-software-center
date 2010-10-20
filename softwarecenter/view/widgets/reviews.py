#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
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

import pygtk
pygtk.require ("2.0")
import gobject
import cairo
import gtk
import os

import pangocairo

from gettext import gettext as _
from mkit import EM, ShapeStar, ShapeRoundedRectangle, VLinkButton, BubbleLabel, floats_from_string


class StarPainter(object):

    FILL_EMPTY      = 0
    FILL_HALF       = 1
    FILL_FULL       = 2

    GLOW_NORMAL     = 3
    GLOW_PRELIGHT   = 4

    def __init__(self):
        self.shape = ShapeStar()
        self.fill = self.FILL_EMPTY
        self.glow = self.GLOW_NORMAL

        self.bg_color = floats_from_string('#989898')     # gray
        self.fg_color = floats_from_string('#D70707')     # crimson red
        self.glow_color = floats_from_string('#FFB500')   # gold
        return

    def set_fill(self, fill):
        self.fill = fill
        return

    def set_glow(self, glow):
        self.glow = glow
        return

    def paint_half_star(self, cr, x, y, w, h):
        # TODO: some rtl switch will be needed here
        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x, y, w, h)
        self._setup_glow(cr)
        cr.stroke()
        cr.set_line_width(2)

        cr.rectangle(x+w*0.5, y-1, w/2+2, h+2)
        cr.clip()

        self.shape.layout(cr, x, y, w, h)
        cr.set_source_rgb(*self.bg_color)
        cr.stroke_preserve()
        cr.fill()
        cairo.Context.reset_clip(cr)

        cr.rectangle(x-1, y-1, w*0.5+1, h+2)
        cr.clip()
        
        self.shape.layout(cr, x, y, w, h)
        cr.set_source_rgb(*self.fg_color)
        cr.stroke_preserve()
        cr.fill_preserve()
        cairo.Context.reset_clip(cr)

        self._setup_gradient(cr, y, h)
        cr.fill()

        cr.restore()
        return

    def paint_star(self, cr, x, y, w, h):
        if self.fill == self.FILL_HALF:
            self.paint_half_star(cr, x, y, w, h)
            return

        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x, y, w, h)

        self._setup_glow(cr)
        cr.stroke_preserve()
        cr.set_line_width(2)

        if self.fill == self.FILL_EMPTY:
            cr.set_source_rgb(*self.bg_color)
        else:
            cr.set_source_rgb(*self.fg_color)

        cr.stroke_preserve()
        cr.fill_preserve()

        self._setup_gradient(cr, y, h)
        cr.fill()

        cr.restore()
        return

    def _setup_glow(self, cr):
        if self.glow == self.GLOW_NORMAL:
            white = self.style.white
            cr.set_source_rgba(white.red_float,
                               white.green_float,
                               white.blue_float, 0.4)
            cr.set_line_width(5)
        else:
            cr.set_source_rgba(*self.glow_color+(0.6,))
            cr.set_line_width(6)
        return

    def _setup_gradient(self, cr, y, h):
        lin = cairo.LinearGradient(0, y, 0, y+h)
        lin.add_color_stop_rgba(0, 1,1,1, 0.5)
        lin.add_color_stop_rgba(1, 1,1,1, 0.05)
        cr.set_source(lin)
        return


class StarWidget(gtk.EventBox, StarPainter):

    def __init__(self, size, is_interactive):
        gtk.EventBox.__init__(self)
        StarPainter.__init__(self)
        self.set_visible_window(False)
        self.set_size_request(*size)

        if is_interactive:
            self._init_event_handling()

        self.connect('expose-event', self._on_expose)
        return

    def _init_event_handling(self):
        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)
        return

    def _on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        self.draw(cr, self.allocation)
        del cr
        return

    def draw(self, cr, a):
        w, h = self.get_size_request()
        x = a.x + (a.width-w)/2
        y = a.y + (a.height-h)/2
        self.paint_star(cr, x, y, w, h)
        return


class StarRating(gtk.Alignment):

    MAX_STARS = 5


    __gsignals__ = {'changed':(gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ())
                    }


    def __init__(self, n_stars=None, spacing=3, star_size=(EM-1,EM-1), is_interactive=False):
        gtk.Alignment.__init__(self, 0.5, 0.5)
        self.set_padding(2, 2, 0, 0)
        self.hbox = gtk.HBox(spacing=spacing)
        self.add(self.hbox)

        self.rating = 0

        self._build(star_size, is_interactive)
        if n_stars != None:
            self.set_rating(n_stars)

    def _build(self, star_size, is_interactive):
        for i in range(self.MAX_STARS):
            star = StarWidget(star_size, is_interactive)
            star.position = i
            self.hbox.pack_start(star, expand=False)
        self.show_all()

    def set_rating(self, n_stars):
        self.rating = n_stars
        #n_stars += 0.5  # XXX: for testing floats only
        acc = self.get_accessible()
        acc.set_name(_("%s star rating") % n_stars)
        acc.set_description(_("%s star rating") % n_stars)

        for i, star in enumerate(self.get_stars()):
            if i < int(n_stars):
                star.set_fill(StarPainter.FILL_FULL)
            elif i == int(n_stars) and n_stars-int(n_stars) > 0:
                star.set_fill(StarPainter.FILL_HALF)
            else:
                star.set_fill(StarPainter.FILL_EMPTY)

        self.emit('changed')
        self.queue_draw()
        return

    def get_rating(self):
        return self.rating

    def get_stars(self):
        return filter(lambda x: isinstance(x, StarWidget), self.hbox.get_children())


class StarRatingSelector(StarRating):

    RATING_WORDS = [_('Hint: Click a star to rate this app'),   # unrated caption
                    _('Unusable'),      # 1 star rating
                    _('Poor'),          # 2 star rating
                    _('Satisfactory'),  # 3 star rating
                    _('Good'),          # 4 star rating
                    _('Exceptional!')]  # 5 star rating


    def __init__(self, n_stars=None, spacing=4, star_size=(EM-1,EM-1)):
        StarRating.__init__(self, n_stars, spacing, star_size, True)

        for star in self.get_stars():
            self._connect_signals(star)

        self.caption = None
        return

    def _on_enter(self, star, event):
        self.set_tentative_rating(star.position+1)
        if self.caption:
            self.caption.set_markup(self.RATING_WORDS[star.position+1])
        return

    def _on_leave(self, star, event):
        gobject.timeout_add(100, self._hover_check_cb)
        return

    def _on_release(self, star, event):
        self.set_rating(star.position+1)
        return

    def _on_focus_in(self, star, event):
        self.set_tentative_rating(star.position+1)
        return True

    def _on_key_press(self, star, event):
        kv = event.keyval
        if kv == gtk.keysyms.space or kv == gtk.keysyms.Return:
            self.set_rating(star.position+1)
        return

    def _connect_signals(self, star):
        star.connect('enter-notify-event', self._on_enter)
        star.connect('leave-notify-event', self._on_leave)
        star.connect('button-release-event', self._on_release)
        star.connect('focus-in-event', self._on_focus_in)
        star.connect('key-press-event', self._on_key_press)
        return

    def _hover_check_cb(self):
        x, y, flags = self.window.get_pointer()
        if not gtk.gdk.region_rectangle(self.hbox.allocation).point_in(x,y):
            self.set_tentative_rating(0)
            if self.caption:
                self.caption.set_markup(self.RATING_WORDS[self.rating])
        return

    def set_caption_widget(self, caption_widget):
        caption_widget.set_markup(self.RATING_WORDS[0])
        self.caption = caption_widget
        return

    def set_tentative_rating(self, n_stars):
        for i, star in enumerate(self.get_stars()):
            if i < int(n_stars):
                star.set_glow(StarPainter.GLOW_PRELIGHT)
            else:
                star.set_glow(StarPainter.GLOW_NORMAL)
        self.queue_draw()
        return


class StarCaption(gtk.Label):

    def __init__(self):
        gtk.Label.__init__(self)
        #self.shape = ShapeRoundedRectangle()
        #self.connect('expose-event', self._on_expose)
        return

    #def _on_expose(self, widget, event):
        #a = widget.allocation
        #cr = widget.window.cairo_create()
        #self.shape.layout(cr, a.x, a.y, a.x+a.width, a.y+a.height, radius=3)
        #light = self.style.light[0]
        #cr.set_source_rgb(light.red_float, light.green_float, light.blue_float)
        #cr.fill()
        #del cr
        #return

    def set_markup(self, markup):
        gtk.Label.set_markup(self, '<small>%s</small>' % markup)
        return


class ReviewStatsContainer(gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, spacing=4)
        self.star_rating = StarRating(star_size=(2*EM,2*EM))
        self.label = gtk.Label()
        self.pack_start(self.star_rating, False)
        self.pack_start(self.label, False, False)
    def set_avg_rating(self, avg_rating):
        self.star_rating.set_rating(avg_rating)
    def set_nr_reviews(self, nr_reviews):
        self.nr_reviews = nr_reviews
        self._update_nr_reviews()
    # internal stuff
    def _update_nr_reviews(self):
        self.label.set_markup(_("%i Ratings") % self.nr_reviews)

if __name__ == "__main__":
    w = ReviewStatsContainer()
    w.set_avg_rating(3.5)
    w.set_nr_reviews(101)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
