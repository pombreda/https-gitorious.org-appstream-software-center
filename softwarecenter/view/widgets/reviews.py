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
from mkit import EM, ShapeStar, ShapeRoundedRectangle, floats_from_string



class StarPainter(object):

    FILL_EMPTY = 0
    FILL_HALF  = 1
    FILL_FULL  = 2

    def __init__(self):
        self.shape = ShapeStar()
        self.fill = self.FILL_FULL
        self.bg_fill = floats_from_string('#484848')
        self.fg_fill = floats_from_string('#D70707')
        return

    def set_fill(self, fill):
        self.fill = fill
        return

    def paint_half_star(self, cr, x, y, w, h):
        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        cr.rectangle(x+w*0.5, y-1, w*0.5+1, h+2)
        cr.clip()

        self.shape.layout(cr, x, y, w, h)
        cr.set_source_rgb(*self.bg_fill)
        cr.stroke_preserve()
        cr.fill()
        cairo.Context.reset_clip(cr)

        cr.rectangle(x-1, y-1, (w+2)*0.5, h+2)
        cr.clip()
        
        self.shape.layout(cr, x, y, w, h)
        cr.set_source_rgb(*self.fg_fill)
        cr.stroke_preserve()
        cr.fill_preserve()
        cairo.Context.reset_clip(cr)

        lin = cairo.LinearGradient(0, y, 0, y+h)
        lin.add_color_stop_rgba(0, 1,1,1, 0.3)
        lin.add_color_stop_rgba(1, 0,0,0, 0.2)
        cr.set_source(lin)
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
        if self.fill == self.FILL_EMPTY:
            cr.set_source_rgb(*self.bg_fill)
        else:
            cr.set_source_rgb(*self.fg_fill)
        cr.stroke_preserve()
        cr.fill_preserve()

        lin = cairo.LinearGradient(0, y, 0, y+h)
        lin.add_color_stop_rgba(0, 1,1,1, 0.3)
        lin.add_color_stop_rgba(1, 0,0,0, 0.2)
        cr.set_source(lin)
        cr.fill()

        cr.restore()
        return


class StarWidget(gtk.EventBox, StarPainter):

    def __init__(self, size):
        gtk.EventBox.__init__(self)
        StarPainter.__init__(self)
        self.set_visible_window(False)
        self.set_size_request(*size)

        self.connect('expose-event', self._on_expose)
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


class StarRating(gtk.HBox):

    MAX_STARS = 5

    def __init__(self, n_stars=None, spacing=3, star_size=(EM-2,EM-2)):
        gtk.HBox.__init__(self, spacing=spacing)
        self._build(star_size)
        if n_stars:
            self.show_stars(n_stars)

    def _build(self, star_size):
        for i in range(self.MAX_STARS):
            star = StarWidget(star_size)
            self.pack_start(star, False)
        self.show_all()

    def show_stars(self, n_stars):
        n_stars += 0.5
        i = 0
        print n_stars
        for child in self.get_children():
            if isinstance(child, StarWidget):
                if i < int(n_stars):
                    child.set_fill(StarPainter.FILL_FULL)
                elif i == int(n_stars):
                    child.set_fill(StarPainter.FILL_HALF)
                else:
                    child.set_fill(StarPainter.FILL_EMPTY)
                i += 1
        return


class ReviewStatsContainer(StarRating):

    def __init__(self):
        StarRating.__init__(self, star_size=(EM,EM))
        self.label = gtk.Label("")
        self.pack_end(self.label, False, False)
        self.connect('expose-event', self._on_expose)
    def _on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        
        return
    def set_avg_rating(self, avg_rating):
        self.show_stars(avg_rating)
    def set_nr_reviews(self, nr_reviews):
        self.nr_reviews = nr_reviews
        self._update_nr_reviews()
    # internal stuff
    def _update_nr_reviews(self):
        self.label.set_markup("<small>(%s)</small>" %  
                              _("%i Ratings") % self.nr_reviews)

if __name__ == "__main__":
    w = ReviewStatsContainer()
    w.set_avg_rating(3.5)
    w.set_nr_reviews(101)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
