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
import gtk
import os

class ReviewStatsContainer(gtk.HBox):

    STAR_IMAGE = "star-yellow"
    DARK_STAR_IMAGE = "star-dark"

    ICON_SIZE = gtk.ICON_SIZE_MENU

    def __init__(self, icon_cache=None):
        gtk.HBox.__init__(self)
        self.avg_rating = None
        self.nr_reviews = None
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
    def set_avg_rating(self, avg_rating):
        self.avg_rating = avg_rating
        self._update_rating()
    def set_nr_reviews(self, nr_reviews):
        self.nr_reviews = nr_reviews
        self._update_nr_reviews()
    # internal stuff
    def _update_nr_reviews(self):
        self.label.set_markup("<small>(%s)</small>" %  
                              _("%i Ratings") % self.nr_reviews)
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
    w = ReviewStatsContainer(icon_cache=icons)
    w.set_avg_rating(3.5)
    w.set_nr_reviews(101)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
