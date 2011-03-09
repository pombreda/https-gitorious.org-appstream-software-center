#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
#
# Authors:
#  Matthew McGowan
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
import datetime
import gobject
import cairo
import gtk
import os
import mkit
import pango
import pangocairo
import logging

import gettext
from gettext import gettext as _

from mkit import EM, Style, ShapeStar, ShapeRoundedRectangle, VLinkButton, floats_from_string

from softwarecenter.utils import get_nice_date_string, upstream_version_compare, upstream_version
from softwarecenter.drawing import color_floats

from softwarecenter.netstatus import network_state_is_connected

from softwarecenter.utils import get_person_from_config
from softwarecenter.enums import *

from softwarecenter.db.reviews import UsefulnessCache


class IStarPainter:

    FILL_EMPTY      = 0
    FILL_HALF       = 1
    FILL_FULL       = 2

    BORDER_OFF = 0
    BORDER_ON = 1

    def __init__(self):
        self.shape = ShapeStar(5, 0.55)

        self.fill = self.FILL_EMPTY
        self.shadow = gtk.SHADOW_NONE
        self.border = self.BORDER_OFF

        self.alpha = 1.0
        self.animate_fill = False

        self.bg_color = floats_from_string('#D6D4D2')     # gray
        self.fg_color = floats_from_string('#FFa000')     # yellow
        self.glow_color = floats_from_string('#FFB500')   # gold
        return

    def set_shadow_type(self, shadow):
        self.shadow = shadow
        return

    def set_fill(self, fill):
        self.fill = fill
        return

    def set_glow(self, glow):
        self.glow = glow
        return

    def paint_half_star(self, cr, widget, state, x, y, w, h):
        raise NotImplemented

    def paint_star(self, cr, widget, state, x, y, w, h):
        raise NotImplemented


class StarPainter(IStarPainter):

    def paint_half_star(self, cr, widget, state, x, y, w, h):

        cr.save()

        if widget.get_direction() != gtk.TEXT_DIR_RTL:
            color1 = self.fg_color
            color2 = self.bg_color

        else:
            color1 = self.bg_color
            color2 = self.fg_color

        cr.rectangle(x, y, w/2, h)
        cr.clip()

        self._paint_star(cr, widget, state, x, y, w, h)

        cairo.Context.reset_clip(cr)

        cr.rectangle(x+w/2, y, w/2, h)
        cr.clip()

        self._paint_star(cr, widget, state, x, y, w, h)

        cairo.Context.reset_clip(cr)
        cr.restore()
        return

    def paint_star(self, cr, widget, state, x, y, w, h):

        if self.fill == self.FILL_HALF:
            self.paint_half_star(cr, widget, state, x, y, w, h)
            return

        self._paint_star(cr, widget, state, x, y, w, h, self.alpha)

        return

    def _paint_star(self, cr, widget, state, x, y, w, h, alpha=1.0):
        cr.save()

        # bevel
        self.shape.layout(cr, x+0.5, y+1.5, w-1, h-1)
        cr.set_line_join(cairo.LINE_CAP_ROUND)
        cr.set_source_rgba(*color_floats(widget.style.white)+(0.85,))
        cr.stroke()

        if self.border == self.BORDER_ON:
            self._paint_star_border(cr, widget, state, x, y, w, h, alpha)

        if self.shadow == gtk.SHADOW_ETCHED_OUT:
            if widget.state != gtk.STATE_ACTIVE:
                self._paint_star_etched_out(cr, widget, state, x, y, w, h, alpha)
            else:
                self._paint_star_etched_in(cr, widget, state, x, y, w, h, alpha)
        else:
            self._paint_star_flat(cr, widget, state, x, y, w, h, alpha)

        if state == gtk.STATE_PRELIGHT and \
            hasattr(self, 'is_interactive') and \
                self.is_interactive:
            self._paint_star_prelight(cr, widget, state, x, y, w, h, alpha)

        cr.restore()
        return

    def _paint_star_border(self, cr, widget, state, x, y, w, h, alpha):
        cr.save()
        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x, y, w, h)
        sel_color = color_floats(widget.style.base[gtk.STATE_SELECTED])

        cr.set_source_rgba(*sel_color+(0.75,))
        cr.set_line_width(4)
        cr.stroke()
        cr.restore()
        return

    def _paint_star_prelight(self, cr, widget, state, x, y, w, h, alpha):
        self.shape.layout(cr, x, y, w, h)

        if self.fill == self.FILL_FULL:
            _alpha = (0.4*alpha,)
        else:
            _alpha = (0.3*alpha,)

        cr.set_source_rgba(*color_floats(widget.style.white)+_alpha)
        cr.fill()
        return

    def _paint_star_flat(self, cr, widget, state, x, y, w, h, alpha):
        self.shape.layout(cr, x, y, w, h)

        if self.fill == self.FILL_EMPTY:
            cr.set_source_rgba(*color_floats(widget.style.mid[state])+(alpha,))
        else:
            cr.set_source_rgba(*self.fg_color+(alpha,))

        cr.fill()
        return

    def _paint_star_etched_out(self, cr, widget, state, x, y, w, h, alpha):
        brown = color_floats('#B54D00')

        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x+1, y+1, w-2, h-2)
        cr.set_source_rgba(*brown+(0.35*alpha,))

        cr.set_line_width(3)
        cr.stroke_preserve()

        cr.set_source_rgba(*brown+(0.6*alpha,))
        cr.set_line_width(2)
        cr.stroke()

        self.shape.layout(cr, x+1, y+1, w-2, h-2)

        if self.fill == self.FILL_EMPTY:
            cr.set_source_rgba(*color_floats(widget.style.mid[state])+(alpha,))
        else:
            cr.set_source_color(widget.style.base[gtk.STATE_SELECTED])

        cr.fill_preserve()

        lin = cairo.LinearGradient(x, y, x, y+h)
        lin.add_color_stop_rgba(0.0, 1,1,1, 0.5*alpha)
        lin.add_color_stop_rgba(1.0, *brown+(0.3*alpha,))

        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1)

        self.shape.layout(cr, x+1.5, y+1.5, w-3, h-3)
        lin = cairo.LinearGradient(x, y, x, y+h)
        lin.add_color_stop_rgba(0.0, 1,1,1, 0.6)
        lin.add_color_stop_rgba(1.0, 1,1,1, 0.15)

        cr.set_source(lin)
        cr.stroke()
        return

    def _paint_star_etched_in(self, cr, widget, state, x, y, w, h, alpha):
        dark = color_floats('#B54D00')

        cr.set_line_join(cairo.LINE_CAP_ROUND)

        self.shape.layout(cr, x+1, y+1, w-2, h-2)
        cr.set_source_rgba(*dark+(0.35*alpha,))

        cr.set_line_width(3)
        cr.stroke_preserve()

        cr.set_source_rgba(*dark+(0.8*alpha,))
        cr.set_line_width(2)
        cr.stroke()

        self.shape.layout(cr, x+1, y+1, w-2, h-2)
        cr.set_source_rgba(*color_floats(widget.style.mid[state])+(alpha,))
        cr.fill_preserve()

        lin = cairo.LinearGradient(x, y, x, y+h)
        lin.add_color_stop_rgba(0.0, 0,0,0, 0.12)
        lin.add_color_stop_rgba(1.0, 0,0,0, 0.05)

        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(2)
        self.shape.layout(cr, x+1, y+1, w-2, h-2)

        darker = color_floats('#6A2D00')
        lin = cairo.LinearGradient(x, y, x, y+h)
        lin.add_color_stop_rgba(0.0, *darker+(0.175,))
        lin.add_color_stop_rgba(1.0, *darker+(0.05,))
        cr.set_source(lin)

        #~ cr.set_source_rgba(*darker+(0.1*alpha,))
        cr.stroke()
        return


class StarWidget(gtk.EventBox, StarPainter):

    def __init__(self, size, is_interactive):
        gtk.EventBox.__init__(self)
        StarPainter.__init__(self)

        self.set_visible_window(False)
        self.set_size_request(*size)

        self.is_interactive = is_interactive
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
        self.paint_star(cr, self, self.state, x, y, w, h)
        return


class SimpleStarRating(gtk.HBox, StarPainter):

    MAX_STARS = 5
    STAR_SIZE = (int(1.25*EM), int(1.25*EM))

    def __init__(self, n_stars=0, spacing=0, star_size=STAR_SIZE):
        gtk.HBox.__init__(self, spacing=spacing)
        StarPainter.__init__(self)

        self.n_stars = n_stars
        self.star_size = star_size
        self.set_max_stars(self.MAX_STARS)

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, widget, event):
        cr = widget.window.cairo_create()
        self.draw(cr, self.allocation)
        del cr
        return

    def _calc_size(self, max_stars):
        sw, sh = self.star_size
        w = max_stars*(sw+self.get_spacing())
        self.set_size_request(w, sh)
        return

    def draw(self, cr, a):
        w, h = self.get_size_request()
        y = a.y + (a.height-h)/2
        sw, sh = self.star_size
        spacing = self.get_spacing()

        n_stars = self.n_stars

        for i in range(self.max_stars):
            if i < int(n_stars):
                self.set_fill(StarPainter.FILL_FULL)
            elif i == int(n_stars) and n_stars-int(n_stars) > 0:
                self.set_fill(StarPainter.FILL_HALF)
            else:
                self.set_fill(StarPainter.FILL_EMPTY)

            x = a.x + i*(sw+spacing)
            self.paint_star(cr, self, self.state, x, y, sw, sh)
        return

    def set_max_stars(self, max_stars):
        self.max_stars = max_stars
        self._calc_size(max_stars)
        return

    def set_rating(self, rating):
        if rating is None: rating = 0
        self.n_stars = rating
        self.queue_draw()
        return


class StarRating(gtk.Alignment):

    MAX_STARS = 5

    __gsignals__ = {'changed':(gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ())
                    }


    def __init__(self, n_stars=0, spacing=0, star_size=(EM,EM), is_interactive=False):
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

    def set_shadow_type(self, shadow):
        for star in self.get_stars():
            star.set_shadow_type(shadow)
        return

    def set_rating(self, n_stars):
        if n_stars is None: n_stars = 0
        self.rating = n_stars

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
                    _('Awful'),         # 1 star rating
                    _('Poor'),          # 2 star rating
                    _('Adequate'),      # 3 star rating
                    _('Good'),          # 4 star rating
                    _('Excellent')]     # 5 star rating


    def __init__(self, n_stars=None, spacing=1, star_size=(4*EM,4*EM)):
        StarRating.__init__(self, n_stars, spacing, star_size, True)

        for star in self.get_stars():
            self._connect_signals(star)

        self.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        self.caption = None
        return

    def _on_enter(self, star, event):
        star.set_state(gtk.STATE_PRELIGHT)
        self.set_tentative_rating(star.position+1)
        if self.caption:
            self.caption.set_markup(self.RATING_WORDS[star.position+1])
        return

    def _on_leave(self, star, event):
        star.set_state(gtk.STATE_NORMAL)
        gobject.timeout_add(100, self._hover_check_cb)
        a = star.allocation
        star.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
        return

    def _on_press(self, star, event):
        a_star_has_focus = filter(lambda s: s.has_focus(),
                                  self.get_stars())
        if a_star_has_focus: star.grab_focus()

        star.set_state(gtk.STATE_ACTIVE)
        a = star.allocation
        star.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
        return

    def _on_release(self, star, event):
        gobject.timeout_add(50, self.set_rating, star.position+1)
        star.set_state(gtk.STATE_PRELIGHT)
        a = star.allocation
        star.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
        return

    def _on_focus_in(self, star, event):
        self.set_tentative_rating(star.position+1)
        return True

    def _on_focus_out(self, star, event):
        self.set_tentative_rating(0)
        return True

    def _on_key_press(self, star, event):
        kv = event.keyval
        if kv == gtk.keysyms.space or kv == gtk.keysyms.Return:
            star.set_state(gtk.STATE_ACTIVE)
            a = star.allocation
            star.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
        elif kv == gtk.keysyms._1:
            self.set_rating(1)
        elif kv == gtk.keysyms._2:
            self.set_rating(2)
        elif kv == gtk.keysyms._3:
            self.set_rating(3)
        elif kv == gtk.keysyms._4:
            self.set_rating(4)
        elif kv == gtk.keysyms._5:
            self.set_rating(5)
        if self.caption:
            self.caption.set_markup(self.RATING_WORDS[self.rating])
        return

    def _on_key_release(self, star, event):
        kv = event.keyval
        if kv == gtk.keysyms.space or kv == gtk.keysyms.Return:
            self.set_rating(star.position+1)
            star.set_state(gtk.STATE_NORMAL)
            a = star.allocation
            star.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
        return

    def _connect_signals(self, star):
        star.connect('enter-notify-event', self._on_enter)
        star.connect('leave-notify-event', self._on_leave)
        star.connect('button-press-event', self._on_press)
        star.connect('button-release-event', self._on_release)
        star.connect('focus-in-event', self._on_focus_in)
        star.connect('focus-out-event', self._on_focus_out)
        star.connect('key-press-event', self._on_key_press)
        star.connect('key-release-event', self._on_key_release)
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
                star.border = StarPainter.BORDER_ON
            else:
                star.border = StarPainter.BORDER_OFF
        a = self.allocation
        self.queue_draw_area(a.x-2, a.y-2, a.width+4, a.height+4)
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
        self.star_rating = StarRating(star_size=(3*EM,3*EM))
        self.star_rating.set_shadow_type(gtk.SHADOW_ETCHED_OUT)

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
        s = gettext.ngettext(
            "%(nr_ratings)i rating",
            "%(nr_ratings)i ratings",
            self.nr_reviews) % { 'nr_ratings' : self.nr_reviews, }
        self.label.set_markup(s)


class UIReviewsList(gtk.VBox):

    __gsignals__ = {
        'new-review':(gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    ()),
        'report-abuse':(gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT,)),
        'submit-usefulness':(gobject.SIGNAL_RUN_FIRST,
                    gobject.TYPE_NONE,
                    (gobject.TYPE_PYOBJECT, bool)),

    }

    def __init__(self, parent):
        gtk.VBox.__init__(self)
        self.logged_in_person = get_person_from_config()

        self._parent = parent
        # this is a list of review data (softwarecenter.db.reviews.Review)
        self.reviews = []
        self.useful_votes = UsefulnessCache()
        self.logged_in_person = None

        label = mkit.EtchedLabel(_("Reviews"))
        label.set_padding(6, 6)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)

        self.new_review = mkit.VLinkButton(_("Write your own review"))
        self.new_review.set_underline(True)

        self.header = hb = gtk.HBox(spacing=mkit.SPACING_MED)
        self.pack_start(hb, False)
        hb.pack_start(label, False)
        hb.pack_end(self.new_review, False, padding=6)

        self.vbox = gtk.VBox(spacing=24)
        self.vbox.set_border_width(6)
        self.pack_start(self.vbox)

        self.new_review.connect('clicked', lambda w: self.emit('new-review'))
        self.show_all()
        return

    def _on_button_new_clicked(self, button):
        self.emit("new-review")

    def _fill(self):
        """ take the review data object from self.reviews and build the
            UI vbox out of them
        """
        self.logged_in_person = get_person_from_config()
        if self.reviews:
            for r in self.reviews:
                pkgversion = self._parent.app_details.version
                review = UIReview(r, pkgversion, self.logged_in_person, self.useful_votes)
                self.vbox.pack_start(review)
        return

    def _be_the_first_to_review(self):
        s = _('Be the first to review it')
        self.new_review.set_label(s)
        self.vbox.pack_start(NoReviewYetWriteOne())
        self.vbox.show_all()
        return
    
    # FIXME: this needs to be smarter in the future as we will
    #        not allow multiple reviews for the same software version
    def _any_reviews_current_user(self):
        for review in self.reviews:
            if self.logged_in_person == review.reviewer_username:
                return True
        return False

    def _add_no_network_connection_msg(self):
        title = _('No Network Connection')
        msg = _('Only cached reviews can be displayed')
        m = EmbeddedMessage(title, msg, 'network-offline')
        self.vbox.pack_start(m)

    # FIXME: instead of clear/add_reviews/finished we should provide
    #        a single show_reviews(reviews_data_list)
    def finished(self):
        """ this needs to be called after add_reviews, it will actually
            show the reviews
        """
        #print 'Review count: %s' % len(self.reviews)

        # network sensitive stuff, only show write_review if connected,
        # add msg about offline cache usage if offline
        is_connected = network_state_is_connected()
        self.new_review.set_sensitive(is_connected)
        if not is_connected:
            self._add_no_network_connection_msg()

        # only show new_review for installed stuff
        is_installed = (self._parent.app_details and
                        self._parent.app_details.pkg_state == PKG_STATE_INSTALLED)
        if is_installed:
            self.new_review.show()
        else:
            self.new_review.hide()

        # always hide spinner and call _fill (fine if there is nothing to do)
        self.hide_spinner()
        self._fill()
        self.vbox.show_all()

        if self.reviews:
            # adjust label if we have reviews
            if self._any_reviews_current_user():
                self.new_review.set_label(_("Write another review"))
            else:
                self.new_review.set_label(_("Write your own review"))
        else:
            # no reviews, either offer to write one or show "none"
            if is_installed and is_connected:
                self._be_the_first_to_review()
            else:
                self.vbox.pack_start(NoReviewYet())
        return

    def add_review(self, review):
        self.reviews.append(review)
        return

    def clear(self):
        self.reviews = []
        for review in self.vbox:
            review.destroy()
        self.new_review.hide()

    # FIXME: ideally we would have "{show,hide}_loading_notice()" to
    #        easily allow changing from e.g. spinner to text
    def show_spinner_with_message(self, message):
        a = gtk.Alignment(0.5, 0.5)

        hb = gtk.HBox(spacing=12)
        a.add(hb)

        spinner = gtk.Spinner()
        spinner.start()

        hb.pack_start(spinner, False)

        l = mkit.EtchedLabel(message)
        l.set_use_markup(True)

        hb.pack_start(l, False)

        self.vbox.pack_start(a, False)
        self.vbox.show_all()
        return
    def hide_spinner(self):
        for child in self.vbox.get_children():
            if isinstance(child, gtk.Alignment):
                child.destroy()
        return

    def draw(self, cr, a):
        for r in self.vbox:
            if isinstance(r, (UIReview)):
                r.draw(cr, r.allocation)
        return

    # mvo: this appears to be not used
    #def get_reviews(self):
    #    return filter(lambda r: type(r) == UIReview, self.vbox.get_children())

class UIReview(gtk.VBox):
    """ the UI for a individual review including all button to mark
        useful/inappropriate etc
    """
    def __init__(self, review_data=None, app_version=None, 
                 logged_in_person=None, useful_votes=None):
        gtk.VBox.__init__(self, spacing=mkit.SPACING_LARGE)

        self.header = gtk.HBox(spacing=mkit.SPACING_MED)
        self.body = gtk.VBox()
        self.footer_split = gtk.VBox()
        self.footer = gtk.HBox()
        
        self.useful = None
        self.yes_like = None
        self.no_like = None
        self.status_box = gtk.HBox()
        self.submit_error_img = gtk.Image()
        self.submit_error_img.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.submit_status_spinner = gtk.Spinner()
        self.submit_status_spinner.set_size_request(12,12)
        self.acknowledge_error = mkit.VLinkButton(_("<small>OK</small>"))
        self.acknowledge_error.set_underline(True)
        self.acknowledge_error.set_subdued(True)
        self.usefulness_error = False

        self.pack_start(self.header, False)
        self.pack_start(self.body, False)
        self.pack_start(self.footer_split, False)
        
        self.logged_in_person = logged_in_person
        self.person = None
        self.id = None

        self._allocation = None

        if review_data:
            self.connect('realize',
                         self._on_realize,
                         review_data,
                         app_version,
                         logged_in_person,
                         useful_votes)
        return

    def _on_realize(self, w, review_data, app_version, logged_in_person, useful_votes):
        self._build(review_data, app_version, logged_in_person, useful_votes)
        return

    def _on_allocate(self, widget, allocation, stars, summary, text, who_when, version_lbl, flag):
        if self._allocation == allocation:
            logging.getLogger("softwarecenter.view.allocation").debug("UIReviewAllocate skipped!")
            return True
        self._allocation = allocation

        summary.set_size_request(max(20, allocation.width - \
                                 stars.allocation.width - \
                                 who_when.allocation.width - 20), -1)

        text.set_size_request(allocation.width, -1)

        if version_lbl:
            version_lbl.set_size_request(allocation.width-flag.allocation.width-20, -1)
        return

    def _on_report_abuse_clicked(self, button):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            reviews.emit("report-abuse", self.id)
    
    def _on_useful_clicked(self, btn, is_useful):
        reviews = self.get_ancestor(UIReviewsList)
        if reviews:
            self._usefulness_ui_update('progress')
            reviews.emit("submit-usefulness", self.id, is_useful)
    
    def _on_error_acknowledged(self, button, current_user_reviewer, useful_total, useful_favorable):
        self.usefulness_error = False
        self._usefulness_ui_update('renew', current_user_reviewer, useful_total, useful_favorable)
    
    def _usefulness_ui_update(self, type, current_user_reviewer=False, useful_total=0, useful_favorable=0):
        self._hide_usefulness_elements()
        #print "_usefulness_ui_update: %s" % type
        if type == 'renew':
            self._build_usefulness_ui(current_user_reviewer, useful_total, useful_favorable)
            return
        if type == 'progress':
            self.submit_status_spinner.start()
            self.submit_status_spinner.show()
            self.status_label = gtk.Label("<small><b>%s</b></small>" % _(u"Submitting now\u2026"))
            self.status_box.pack_start(self.submit_status_spinner, False)
            self.status_label.set_use_markup(True)
            self.status_label.set_padding(2,0)
            self.status_box.pack_start(self.status_label,False)
            self.status_label.show()
        if type == 'error':
            self.submit_error_img.show()
            self.status_label = gtk.Label("<small><b>%s</b></small>" % _("Error submitting usefulness"))
            self.status_box.pack_start(self.submit_error_img, False)
            self.status_label.set_use_markup(True)
            self.status_label.set_padding(2,0)
            self.status_box.pack_start(self.status_label,False)
            self.status_label.show()
            self.acknowledge_error.show()
            self.status_box.pack_start(self.acknowledge_error,False)
            self.acknowledge_error.connect('clicked', self._on_error_acknowledged, current_user_reviewer, useful_total, useful_favorable)
        self.status_box.show()
        self.footer.pack_start(self.status_box, False)
        return

    def _hide_usefulness_elements(self):
        """ hide all usefulness elements """
        for attr in ["useful", "yes_like", "no_like", "submit_status_spinner",
                     "submit_error_img", "status_box", "status_label",
                     "acknowledge_error", "yes_no_separator"
                     ]:
            widget = getattr(self, attr, None)
            if widget:
                widget.hide()
        return

    def _get_datetime_from_review_date(self, raw_date_str):
        # example raw_date str format: 2011-01-28 19:15:21
        return datetime.datetime.strptime(raw_date_str, '%Y-%m-%d %H:%M:%S')

    def _build(self, review_data, app_version, logged_in_person, useful_votes):

        # all the attributes of review_data may need markup escape, 
        # depening on if they are used as text or markup
        self.id = review_data.id
        self.person = review_data.reviewer_username
        displayname = review_data.reviewer_displayname
        # example raw_date str format: 2011-01-28 19:15:21
        cur_t = self._get_datetime_from_review_date(review_data.date_created)

        app_name = review_data.app_name
        review_version = review_data.version
        self.useful_total = useful_total = review_data.usefulness_total
        useful_favorable = review_data.usefulness_favorable
        useful_submit_error = review_data.usefulness_submit_error

        dark_color = self.style.dark[gtk.STATE_NORMAL]
        m = self._whom_when_markup(self.person, displayname, cur_t, dark_color)

        who_when = mkit.EtchedLabel(m)
        who_when.set_use_markup(True)

        summary = mkit.EtchedLabel('<b>%s</b>' % gobject.markup_escape_text(review_data.summary))
        summary.set_use_markup(True)
        summary.set_ellipsize(pango.ELLIPSIZE_END)
        summary.set_selectable(True)
        summary.set_alignment(0, 0.5)

        text = gtk.Label(review_data.review_text)
        text.set_line_wrap(True)
        text.set_selectable(True)
        text.set_alignment(0, 0)

        stars = SimpleStarRating(review_data.rating)

        self.header.pack_start(stars, False)
        self.header.pack_start(summary, False)
        self.header.pack_end(who_when, False)
        self.body.pack_start(text, False)
        
        #if review version is different to version of app being displayed, 
        # alert user
        version_lbl = None
        if (review_version and 
            upstream_version_compare(review_version, app_version) != 0):
            version_string = _("This review was written for a different version of %(app_name)s (Version: %(version)s)") % { 
                'app_name' : app_name,
                'version' : gobject.markup_escape_text(upstream_version(review_version))
                }

            m = '<small><i><span color="%s">%s</span></i></small>'
            version_lbl = gtk.Label(m % (dark_color.to_string(), version_string))
            version_lbl.set_use_markup(True)
            version_lbl.set_padding(0,3)
            version_lbl.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
            version_lbl.set_alignment(0, 0.5)
            self.footer_split.pack_start(version_lbl, False)

        self.footer_split.pack_start(self.footer, False)

        current_user_reviewer = False
        if self.person == self.logged_in_person:
            current_user_reviewer = True

        self._build_usefulness_ui(current_user_reviewer, useful_total,
                                  useful_favorable, useful_votes, useful_submit_error)

        # Translators: This link is for flagging a review as inappropriate.
        # To minimize repetition, if at all possible, keep it to a single word.
        # If your language has an obvious verb, it won't need a question mark.
        self.complain = mkit.VLinkButton('<small>%s</small>' % _('Inappropriate?'))
        self.complain.set_subdued(True)
        self.complain.set_underline(True)
        self.footer.pack_end(self.complain, False)
        self.complain.connect('clicked', self._on_report_abuse_clicked)
        # FIXME: dynamically update this on network changes
        self.complain.set_sensitive(network_state_is_connected())
        self.body.connect('size-allocate', self._on_allocate, stars, 
                          summary, text, who_when, version_lbl, self.complain)
        return
    
    def _build_usefulness_ui(self, current_user_reviewer, useful_total, 
                             useful_favorable, useful_votes, usefulness_submit_error=False):
        if usefulness_submit_error:
            self._usefulness_ui_update('error', current_user_reviewer, 
                                       useful_total, useful_favorable)
        else:
            already_voted = useful_votes.check_for_usefulness(self.id)
            #get correct label based on retrieved usefulness totals and 
            # if user is reviewer
            self.useful = self._get_usefulness_label(
                current_user_reviewer, useful_total, useful_favorable, already_voted)
            self.useful.set_use_markup(True)
            #vertically centre so it lines up with the Yes and No buttons
            self.useful.set_alignment(0, 0.5)

            self.useful.show()
            self.footer.pack_start(self.useful, False, padding=3)
            # add here, but only populate if its not the own review
            self.likebox = gtk.HBox()
            if already_voted == None and not current_user_reviewer:
                self.yes_like = mkit.VLinkButton('<small>%s</small>' % _('Yes'))
                self.no_like = mkit.VLinkButton('<small>%s</small>' % _('No'))
                self.yes_like.set_underline(True)
                self.no_like.set_underline(True)
                self.yes_like.connect('clicked', self._on_useful_clicked, True)
                self.no_like.connect('clicked', self._on_useful_clicked, False)
                self.yes_no_separator = gtk.Label("<small>/</small>")
                self.yes_no_separator.set_use_markup(True)
                
                self.yes_like.show()
                self.no_like.show()
                self.yes_no_separator.show()
                self.likebox.set_spacing(3)
                self.likebox.pack_start(self.yes_like, False)
                self.likebox.pack_start(self.yes_no_separator, False)
                self.likebox.pack_start(self.no_like, False)
                self.footer.pack_start(self.likebox, False)
            # always update network status (to keep the code simple)
            self._update_likebox_based_on_network_state()
        return

    def _update_likebox_based_on_network_state(self):
        """ show/hide yes/no based on network connection state """
        # FIXME: make this dynamic shode/hide on network changes
        # FIXME2: make ti actually work, later show_all() kill it
        #         currently
        if network_state_is_connected():
            self.likebox.show()
            self.useful.show()
        else:
            self.likebox.hide()
            # showing "was this useful is not interessting"
            if self.useful_total == 0:
                self.useful.hide()
    
    def _get_usefulness_label(self, current_user_reviewer, 
                              useful_total,  useful_favorable, already_voted):
        '''returns gtk.Label() to be used as usefulness label depending 
           on passed in parameters
        '''
        if already_voted == None:
            if useful_total == 0 and current_user_reviewer:
                s = ""
            elif useful_total == 0:
                # no votes for the review yet
                s = _("Was this review helpful?")
            elif current_user_reviewer:
                # user has already voted for the review
                s = gettext.ngettext(
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful.",
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful.",
                    useful_total) % { 'useful_total' : useful_total,
                                    'useful_favorable' : useful_favorable,
                                    }
            else:
                # user has not already voted for the review
                s = gettext.ngettext(
                    "%(useful_favorable)s of %(useful_total)s person "
                    "found this review helpful. Did you?",
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful. Did you?",
                    useful_total) % { 'useful_total' : useful_total,
                                    'useful_favorable' : useful_favorable,
                                    }
        else:
        #only display these special strings if the user voted either way
            if already_voted:
                #if voted True
                s = _("You have already marked this review as helpful")
            else:
                #if voted False
                s = _("You have already marked this review as unhelpful")
        
        return gtk.Label('<small>%s</small>' % s)

    def _whom_when_markup(self, person, displayname, cur_t, dark_color):
        nice_date = get_nice_date_string(cur_t)
        dt = datetime.datetime.utcnow() - cur_t

        # prefer displayname if available
        correct_name = displayname or person

        if person == self.logged_in_person:
            m = '<span color="%s"><b>%s (%s)</b>, %s</span>' % (
                dark_color.to_string(),
                gobject.markup_escape_text(correct_name),
                # TRANSLATORS: displayed in a review after the persons name,
                # e.g. "Wonderful text based app" mvo (that's you) 2011-02-11"
                _("that's you"),
                gobject.markup_escape_text(nice_date))
        else:
            m = '<span color="%s"><b>%s</b>, %s</span>' % (
                dark_color.to_string(),
                gobject.markup_escape_text(correct_name),
                gobject.markup_escape_text(nice_date))

        return m

    def draw(self, cr, a):
        cr.save()
        if not self.person == self.logged_in_person:
            return

        cr.rectangle(a)

        color = mkit.floats_from_gdkcolor(self.style.mid[self.state])
        cr.set_source_rgba(*color+(0.2,))

        cr.fill()

        cr.restore()

class EmbeddedMessage(UIReview):

    def __init__(self, title='', message='', icon_name=''):
        UIReview.__init__(self)
        self.label = None
        self.image = None
        
        a = gtk.Alignment(0.5, 0.5)
        self.body.pack_start(a, False)

        hb = gtk.HBox(spacing=12)
        a.add(hb)

        if icon_name:
            self.image = gtk.image_new_from_icon_name(icon_name,
                                                      gtk.ICON_SIZE_DIALOG)
            hb.pack_start(self.image, False)

        self.label = gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_alignment(0, 0.5)

        if title:
            self.label.set_markup('<b><big>%s</big></b>\n%s' % (title, message))
        else:
            self.label.set_markup(message)

        hb.pack_start(self.label)

        self.show_all()
        return

    def draw(self, cr, a):
        cr.save()
        cr.rectangle(a)
        color = mkit.floats_from_gdkcolor(self.style.mid[self.state])
        cr.set_source_rgba(*color+(0.2,))
        cr.fill()
        cr.restore()


class NoReviewYet(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is not installed """
    def __init__(self, *args, **kwargs):
        # TRANSLATORS: displayed if there are no reviews for the app yet
        #              and the user does not have it installed
        msg = _("None yet")
        EmbeddedMessage.__init__(self, message=msg)


class NoReviewYetWriteOne(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is installed """
    def __init__(self, *args, **kwargs):

        # TRANSLATORS: displayed if there are no reviews yet and the user
        #              has the app installed
        title = _('Want to be awesome?')
        msg = _('Be the first to contribute a review for this application')

        EmbeddedMessage.__init__(self, title, msg, 'face-glasses')
        return



if __name__ == "__main__":
    w = StarRatingSelector()
    #~ w.set_avg_rating(3.5)
    #~ w.set_nr_reviews(101)

    l = gtk.Label('focus steeler')
    l.set_selectable(True)

    vb = gtk.VBox(spacing=6)
    vb.pack_start(l)
    vb.pack_start(w)

    win = gtk.Window()
    win.add(vb)
    win.show_all()
    win.connect('destroy', gtk.main_quit)

    gtk.main()
