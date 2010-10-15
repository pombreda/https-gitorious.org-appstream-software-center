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
from mkit import EM, ShapeStar, floats_from_string



class StarPainter(object):

    def __init__(self):
        self.shape = ShapeStar()
        #self.fraction = 1.0    # maybe we could have partially filled stars for like 3.5/5 scenarios

        #self.bg_fill = floats_from_string('#949494')
        #self.bg_line = floats_from_string('#484848')

        self.fg_fill = floats_from_string('#DC3300')
        #self.fg_line = floats_from_string('#912000')
        return

    def paint_star(self, cr, x, y, w, h):
        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x, y, w, h)
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


class DarkStarWidget(StarWidget):

    def __init__(self, size):
        StarWidget.__init__(self, size)
        
        self.fg_fill = floats_from_string('#C2C2C2')


class StarRating(gtk.HBox):

    def __init__(self, n_stars=None, spacing=3, star_size=(EM,EM)):
        gtk.HBox.__init__(self, spacing=spacing)
        self.star_size = star_size
        if n_stars:
            self.show_stars(n_stars)
    def show_stars(self, n_stars):
        # kill old
        
        self.foreach(lambda w: isinstance(w, (StarWidget, DarkStarWidget)) and w.destroy())
        for i in range(n_stars):
            self.pack_start(StarWidget(self.star_size), False)
        for i in range(5-n_stars):
            self.pack_start(DarkStarWidget(self.star_size), False)
        self.show_all()
        return

class ReviewStatsContainer(StarRating):

    STAR_IMAGE = "star-yellow"
    DARK_STAR_IMAGE = "star-dark"

    ICON_SIZE = gtk.ICON_SIZE_MENU

    def __init__(self):
        StarRating.__init__(self)
        self.label = gtk.Label("")
        self.pack_end(self.label, False, False)
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
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/software-center/images/")
    if os.path.exists("data/images/"):
        icons.append_search_path("data/images")
    w = ReviewStatsContainer(icon_cache=icons)
    w.set_avg_rating(3.5)
    w.set_nr_reviews(101)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
