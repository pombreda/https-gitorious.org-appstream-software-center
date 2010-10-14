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
from mkit import ShapeStar, floats_from_string



class Star(gtk.EventBox):

    def __init__(self, size=(11,11)):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_size_request(*size)

        self.size_request = size
        self.shape = ShapeStar()
        self.fraction = 1.0

        self.fg_fill = floats_from_string('#DC3300')
        self.fg_line = floats_from_string('#912000')

        #self.bg_fill = floats_from_string('#949494')
        #self.bg_line = floats_from_string('#484848')

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        self.draw(cr, self.allocation)
        del cr
        return

    def draw(self, cr, a):
        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        w, h = self.size_request
        x = a.x + (a.width-self.size_request[0])/2
        y = a.y + (a.height-self.size_request[1])/2

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


class StarRatingWidget(gtk.HBox):

    def __init__(self, n_stars, spacing=3):
        gtk.HBox.__init__(self, spacing=spacing)
        for i in range(n_stars):
            self.pack_start(Star(), False)
        self.show_all()
        return


class ReviewStatsContainer(gtk.HBox):

    STAR_IMAGE = "star-yellow"
    DARK_STAR_IMAGE = "star-dark"

    ICON_SIZE = gtk.ICON_SIZE_MENU
    STAR_SIZE = 16

    def __init__(self, avg_rating=0, nr_reviews=0, icon_cache=None):
        gtk.HBox.__init__(self)
        self.avg_rating = avg_rating
        self.nr_reviews = nr_reviews
        if not icon_cache:
            icons = gtk.icon_theme_get_default()
            icons.append_search_path("/usr/share/software-center/images/")
        else:
            icons = icon_cache
        for i in range(1,6):
            name = "image_review_star%i" % i
            setattr(self, name, gtk.Image())
            self.pack_start(getattr(self, name), False, False)
        self.label = gtk.Label("")
        self.pack_start(self.label, False, False)
        self._update_nr_reviews()
        self._update_rating()
    def set_avg_rating(self, avg_rating):
        self.avg_rating = avg_rating
        self._update_rating()
    def set_nr_reviews(self, nr_reviews):
        self.nr_reviews = nr_reviews
        self._update_nr_reviews()
    # internal stuff
    def _update_nr_reviews(self):
        self.label.set_markup("<small>(%s)</small>" % self.nr_reviews)
    def _update_rating(self):
        for i in range(1, self.avg_rating+1):
            img = getattr(self, "image_review_star%i" % i)
            img.set_from_icon_name(self.STAR_IMAGE, self.ICON_SIZE)
        for i in range(self.avg_rating+1, 6):
            img = getattr(self, "image_review_star%i" % i)
            img.set_from_icon_name(self.DARK_STAR_IMAGE, self.ICON_SIZE)

if __name__ == "__main__":
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/software-center/images/")
    if os.path.exists("data/images/"):
        icons.append_search_path("data/images")
    w = ReviewStatsContainer(3.5, 101, icon_cache=icons)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
