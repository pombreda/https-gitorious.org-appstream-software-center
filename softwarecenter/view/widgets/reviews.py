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

import gettext
from gettext import gettext as _

from mkit import EM, ShapeStar, ShapeRoundedRectangle, VLinkButton, floats_from_string
from softwarecenter.utils import get_nice_date_string, upstream_version_compare, upstream_version

from softwarecenter.netstatus import network_state_is_connected

from softwarecenter.utils import get_person_from_config
from softwarecenter.enums import *

class IStarPainter:

    FILL_EMPTY      = 0
    FILL_HALF       = 1
    FILL_FULL       = 2

    GLOW_NORMAL     = 3
    GLOW_PRELIGHT   = 4

    def __init__(self):
        self.shape = ShapeStar(5, 0.55)
        self.fill = self.FILL_EMPTY
        self.glow = self.GLOW_NORMAL

        self.bg_color = floats_from_string('#989898')     # gray
        self.fg_color = floats_from_string('#FFa000')     # yellow
        self.glow_color = floats_from_string('#FFB500')   # gold
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


class StarPainterFlat(IStarPainter):

    def paint_half_star(self, cr, widget, state, x, y, w, h):
        cr.save()
        #cr.set_line_join(cairo.LINE_CAP_ROUND)

        cr.rectangle(x+w*0.5, y-1, w/2+2, h+2)
        cr.clip()

        if widget.get_direction() != gtk.TEXT_DIR_RTL:
#            color1 = widget.style.mid[state]
#            color2 = widget.style.text[state]
            color1 = self.bg_color
            color2 = self.fg_color

        else:
#            color1 = widget.style.text[state]
#            color2 = widget.style.mid[state]
            color1 = self.fg_color
            color2 = self.bg_color

        self.shape.layout(cr, x, y, w, h)
#        cr.set_source_color(color1)
        cr.set_source_rgb(*color1)
        cr.fill()
        cairo.Context.reset_clip(cr)

        cr.rectangle(x-1, y-1, w*0.5+1, h+2)
        cr.clip()

        self.shape.layout(cr, x, y, w, h)
#        cr.set_source_color(color2)
        cr.set_source_rgb(*color2)
        cr.fill()
        cairo.Context.reset_clip(cr)

        cr.restore()
        return

    def paint_star(self, cr, widget, state, x, y, w, h):
        if self.fill == self.FILL_HALF:
            self.paint_half_star(cr, widget, state, x, y, w, h)
            return

        cr.save()

        self.shape.layout(cr, x, y, w, h)
        if self.fill == self.FILL_EMPTY:
            cr.set_source_color(widget.style.mid[state])
        else:
            if state != gtk.STATE_SELECTED:
#                cr.set_source_color(widget.style.base[gtk.STATE_SELECTED])
                cr.set_source_rgb(*self.fg_color)
            else:
#                cr.set_source_color(widget.style.base[gtk.STATE_NORMAL])
                cr.set_source_rgb(*self.bg_color)

        cr.fill()

        cr.restore()
        return


class StarPainter(IStarPainter):

    def paint_half_star(self, cr, widget, state, x, y, w, h):
        # TODO: some rtl switch will be needed here
        cr.save()

        if widget.get_direction() != gtk.TEXT_DIR_RTL:
#            color1 = widget.style.mid[state]
#            color2 = widget.style.text[state]
            color1 = self.bg_color
            color2 = self.fg_color

        else:
#            color1 = widget.style.text[state]
#            color2 = widget.style.mid[state]
            color1 = self.fg_color
            color2 = self.bg_color

        self.shape.layout(cr, x, y, w, h)
        self._setup_glow(cr, widget)
        cr.stroke()
        cr.set_line_width(2)

        cr.rectangle(x+w*0.5, y-1, w/2+2, h+2)
        cr.clip()

        self.shape.layout(cr, x, y, w, h)
#        cr.set_source_color(widget.style.mid[state])
        cr.set_source_rgb(*color1)
        cr.stroke_preserve()
        cr.fill()
        cairo.Context.reset_clip(cr)

        cr.rectangle(x-1, y-1, w*0.5+1, h+2)
        cr.clip()
        
        self.shape.layout(cr, x, y, w, h)
#        cr.set_source_color(widget.style.base[gtk.STATE_SELECTED])
        cr.set_source_rgb(*color2)
        cr.stroke_preserve()
        cr.fill_preserve()
        cairo.Context.reset_clip(cr)

        self._setup_gradient(cr, y, h)
        cr.fill()

        cr.restore()
        return

    def paint_star(self, cr, widget, state, x, y, w, h):
        if self.fill == self.FILL_HALF:
            self.paint_half_star(cr, widget, state, x, y, w, h)
            return

        cr.save()

        self.shape.layout(cr, x, y, w, h)

        self._setup_glow(cr, widget)
        cr.stroke_preserve()
        cr.set_line_width(2)

        if self.fill == self.FILL_EMPTY:
#            cr.set_source_color(widget.style.mid[state])
            cr.set_source_rgb(*self.bg_color)
        else:
#            cr.set_source_color(widget.style.base[gtk.STATE_SELECTED])
            cr.set_source_rgb(*self.fg_color)

        cr.stroke_preserve()
        cr.fill_preserve()

        self._setup_gradient(cr, y, h)
        cr.fill()

        cr.restore()
        return

    def _setup_glow(self, cr, widget):
        if self.glow == self.GLOW_NORMAL:
            white = widget.style.white
            cr.set_source_rgba(white.red_float,
                               white.green_float,
                               white.blue_float, 0.33)
            cr.set_line_width(5)
        else:
            glow = widget.style.base[gtk.STATE_SELECTED]
            cr.set_source_rgba(glow.red_float,
                               glow.green_float,
                               glow.blue_float, 0.6)
            cr.set_line_width(6)
        return

    def _setup_gradient(self, cr, y, h):
        lin = cairo.LinearGradient(0, y, 0, y+h)
        lin.add_color_stop_rgba(0, 1,1,1, 0.3)
        lin.add_color_stop_rgba(1, 1,1,1, 0.02)
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
        self.paint_star(cr, self, self.state, x, y, w, h)
        return


class StarRating(gtk.Alignment):

    MAX_STARS = 5

    __gsignals__ = {'changed':(gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE,
                               ())
                    }


    def __init__(self, n_stars=None, spacing=3, star_size=(EM,EM), is_interactive=False):
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
                    _('Awful'),         # 1 star rating
                    _('Poor'),          # 2 star rating
                    _('Adequate'),      # 3 star rating
                    _('Good'),          # 4 star rating
                    _('Excellent')]     # 5 star rating


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

    def _on_focus_out(self, star, event):
        for star in self.get_stars():
            if star.has_focus(): return
        self.set_tentative_rating(0)
        return True

    def _on_key_press(self, star, event):
        kv = event.keyval
        if kv == gtk.keysyms.space or kv == gtk.keysyms.Return:
            self.set_rating(star.position+1)
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

    def _connect_signals(self, star):
        star.connect('enter-notify-event', self._on_enter)
        star.connect('leave-notify-event', self._on_leave)
        star.connect('button-release-event', self._on_release)
        star.connect('focus-in-event', self._on_focus_in)
        star.connect('focus-out-event', self._on_focus_out)
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
        self.star_rating = StarRating(star_size=(int(2.5*EM),int(2.5*EM)))
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
        self.reviews = []
        self.logged_in_person = None

        label = mkit.EtchedLabel()
        label.set_padding(6, 6)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        markup = _("Reviews")
        label.set_markup(markup)

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
        self.logged_in_person = get_person_from_config()
        if self.reviews:
            for r in self.reviews:
                pkgversion = self._parent.app_details.version
                review = UIReview(r, pkgversion, self.logged_in_person)
                self.vbox.pack_start(review)


        return

    def _be_the_first_to_review(self):
        s = _('Be the first to review it')
        self.new_review.set_label(s)
        self.vbox.pack_start(NoReviewYet())
        self.vbox.show_all()
        return
    
    def _any_reviews_current_user(self):
        for review in self.reviews:
            if self.logged_in_person == review.reviewer_username:
                return True
        return False

    def finished(self):
        #print 'Review count: %s' % len(self.reviews)
        is_installed = (self._parent.app_details and
                        self._parent.app_details.pkg_state == PKG_STATE_INSTALLED)

        # only show new_review for installed stuff
        if is_installed:
            self.new_review.show()
            if not self.reviews:
                self._be_the_first_to_review()
        else:
            self.new_review.hide()

        # hide spinner 
        self.hide_spinner()
        self._fill()
        self.vbox.show_all()

        # setup label accordingly (maybe hidden)
        if self.reviews:
            if self._any_reviews_current_user():
                self.new_review.set_label(_("Write another review"))
            else:
                self.new_review.set_label(_("Write your own review"))
        else:
            s = '%s' % _("None yet")
            self.vbox.pack_start(EmbeddedMessage(message=s))

        return

    def set_width(self, w):
        for r in self.vbox:
            r.body.set_size_request(w, -1)
        return

    def add_review(self, review):
        self.reviews.append(review)
        return

    def clear(self):
        self.reviews = []
        for review in self.vbox:
            review.destroy()
        self.new_review.hide()

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
#        cr.save()

#        color = color_floats('#FFE879')

#        a = self.allocation
#        rounded_rect(cr, a.x, a.y, a.width, a.height, 5)
#        cr.set_source_rgba(*color+(0.225,))
#        cr.fill()

#        a = self.header.allocation
#        rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))

#        cr.set_source_rgba(*color+(0.5,))
#        cr.fill()

#        a = self.allocation
#        cr.save()
#        rounded_rect(cr, a.x+0.5, a.y+0.5, a.width-1, a.height-1, 5)
#        cr.set_source_rgba(*color+(0.4,))
#        cr.set_line_width(1)
#        cr.stroke()
#        cr.restore()

        for r in self.vbox:
            if isinstance(r, (UIReview)):
                r.draw(cr, r.allocation)
        return

    def get_reviews(self):
        return filter(lambda r: not isinstance(r, EmbeddedMessage) \
                        and isinstance(r, UIReview), self.vbox.get_children())

class UIReview(gtk.VBox):
    
    def __init__(self, review_data=None, app_version=None, logged_in_person=None):
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
                         logged_in_person)
        return

    def _on_realize(self, w, review_data, app_version, logged_in_person):
        self._build(review_data, app_version, logged_in_person)
        return

    def _on_allocate(self, widget, allocation, stars, summary, who_when, version_lbl, flag):
        if self._allocation == allocation:
            logging.getLogger("softwarecenter.view.allocation").debug("UIReviewAllocate skipped!")
            return True
        self._allocation = allocation

        summary.set_size_request(max(20, allocation.width - \
                                 stars.allocation.width - \
                                 who_when.allocation.width - 20), -1)
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
            o = getattr(self, attr, None)
            if o:
                o.hide()
        return

    def _get_datetime_from_review_date(self, raw_date_str):
        # example raw_date str format: 2011-01-28 19:15:21
        return datetime.datetime.strptime(raw_date_str, '%Y-%m-%d %H:%M:%S')

    def _build(self, review_data, app_version, logged_in_person):

        # all the attributes of review_data may need markup escape, 
        # depening on if they are used as text or markup
        self.id = review_data.id
        self.person = review_data.reviewer_username
        # example raw_date str format: 2011-01-28 19:15:21
        cur_t = self._get_datetime_from_review_date(review_data.date_created)

        app_name = review_data.app_name
        review_version = review_data.version
        useful_total = review_data.usefulness_total
        useful_favorable = review_data.usefulness_favorable
        useful_submit_error = review_data.usefulness_submit_error

        dark_color = self.style.dark[gtk.STATE_NORMAL]
        m = self._whom_when_markup(self.person, cur_t, dark_color)

        who_when = mkit.EtchedLabel(m)
        who_when.set_use_markup(True)

        summary = mkit.EtchedLabel('<b>%s</b>' % gobject.markup_escape_text(review_data.summary))
        summary.set_use_markup(True)
        summary.set_ellipsize(pango.ELLIPSIZE_END)
        summary.set_alignment(0, 0.5)

        text = gtk.Label(review_data.review_text)
        text.set_line_wrap(True)
        text.set_selectable(True)
        text.set_alignment(0, 0)

        stars = StarRating(review_data.rating)

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

        self._build_usefulness_ui(current_user_reviewer, useful_total, useful_favorable, useful_submit_error)

        # Translators: This link is for flagging a review as inappropriate.
        # To minimize repetition, if at all possible, keep it to a single word.
        # If your language has an obvious verb, it won't need a question mark.
        self.complain = mkit.VLinkButton('<small>%s</small>' % _('Inappropriate?'))
        self.complain.set_subdued(True)
        self.complain.set_underline(True)
        self.footer.pack_end(self.complain, False)
        self.complain.connect('clicked', self._on_report_abuse_clicked)

        self.body.connect('size-allocate', self._on_allocate, stars, summary, who_when, version_lbl, self.complain)
        return
    
    def _build_usefulness_ui(self, current_user_reviewer, useful_total, useful_favorable, usefulness_submit_error=False):
        if usefulness_submit_error:
            self._usefulness_ui_update('error', current_user_reviewer, useful_total, useful_favorable)
        else:
            #get correct label based on retrieved usefulness totals and if user is reviewer
            self.useful = self._get_usefulness_label(current_user_reviewer, useful_total, useful_favorable)
            self.useful.set_use_markup(True)
            #vertically centre so it lines up with the Yes and No buttons
            self.useful.set_alignment(0, 0.5)

            self.useful.show()
            self.footer.pack_start(self.useful, False, padding=3)
            if not current_user_reviewer:
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
                self.likebox = gtk.HBox()
                self.likebox.set_spacing(3)
                self.likebox.pack_start(self.yes_like, False)
                self.likebox.pack_start(self.yes_no_separator, False)
                self.likebox.pack_start(self.no_like, False)
                self.likebox.show()
                self.footer.pack_start(self.likebox, False)
        return

    
    def _get_usefulness_label(self, current_user_reviewer, useful_total, useful_favorable):
        '''returns gtk.Label() to be used as usefulness label depending on passed in parameters'''
        if useful_total == 0 and current_user_reviewer:
            s = ""
        elif useful_total == 0:
            s = _("Was this review hepful?")
        elif current_user_reviewer:
            s = gettext.ngettext(
                "%(useful_favorable)s of %(useful_total)s person "
                "found this review helpful.",
                "%(useful_favorable)s of %(useful_total)s people "
                "found this review helpful.",
                useful_total) % { 'useful_total' : useful_total,
                                  'useful_favorable' : useful_favorable,
                                }
        else:
            s = gettext.ngettext(
                "%(useful_favorable)s of %(useful_total)s person "
                "found this review helpful. Did you?",
                "%(useful_favorable)s of %(useful_total)s people "
                "found this review helpful. Did you?",
                useful_total) % { 'useful_total' : useful_total,
                                'useful_favorable' : useful_favorable,
                                }
        
        return gtk.Label('<small>%s</small>' % s)

    def _whom_when_markup(self, person, cur_t, dark_color):
        nice_date = get_nice_date_string(cur_t)
        dt = datetime.datetime.utcnow() - cur_t

        if person == self.logged_in_person:
            m = '<span color="%s"><b>%s (%s)</b>, %s</span>' % (
                dark_color.to_string(),
                gobject.markup_escape_text(person),
                # TRANSLATORS: displayed in a review after the persons name,
                # e.g. "Wonderful text based app" mvo (that's you) 2011-02-11"
                _("that's you"),
                gobject.markup_escape_text(nice_date))
        else:
            m = '<span color="%s"><b>%s</b>, %s</span>' % (
                dark_color.to_string(),
                gobject.markup_escape_text(person),
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
            i = gtk.image_new_from_icon_name(icon_name, gtk.ICON_SIZE_DIALOG)
            hb.pack_start(i, False)
            # this is used in the UI tests
            self.image = i

        l = gtk.Label()
        l.set_size_request(300, -1)
        l.set_line_wrap(True)
        l.set_alignment(0, 0.5)
        # this is used in the UI tests
        self.label = l

        l.set_markup('<b><big>%s</big></b>\n%s' % (title, message))

        hb.pack_start(l)

        self.show_all()
        return

    def draw(self, *args, **kwargs):
        return


class NoReviewYet(EmbeddedMessage):
    """ represents if there are no reviews yet """
    def __init__(self, *args, **kwargs):

        # TRANSLATORS: displayed if there are no reviews yet
        title = _('Want to be awesome?')
        msg = _('Be the first to contribute a review for this application')

        EmbeddedMessage.__init__(self, title, msg, 'face-glasses')
        return



if __name__ == "__main__":
    w = ReviewStatsContainer()
    w.set_avg_rating(3.5)
    w.set_nr_reviews(101)
    w.show_all()
    win = gtk.Window()
    win.add(w)
    win.show()

    gtk.main()
