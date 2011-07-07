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

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, Pango

from stars import Star

import datetime
import logging

import gettext
from gettext import gettext as _

from softwarecenter.utils import (
    get_language,
    get_person_from_config,
    get_nice_date_string, 
    upstream_version_compare, 
    upstream_version, 
    )

from softwarecenter.netstatus import network_state_is_connected
from softwarecenter.enums import PkgStates, REVIEWS_BATCH_PAGE_SIZE
from softwarecenter.backend.reviews import UsefulnessCache

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.buttons import Link

LOG_ALLOCATION = logging.getLogger("softwarecenter.ui.Gtk.get_allocation()")


class UIReviewsList(Gtk.VBox):

    __gsignals__ = {
        'new-review':(GObject.SignalFlags.RUN_FIRST,
                    None,
                    ()),
        'report-abuse':(GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT,)),
        'submit-usefulness':(GObject.SignalFlags.RUN_FIRST,
                    None,
                    (GObject.TYPE_PYOBJECT, bool)),
        'more-reviews-clicked':(GObject.SignalFlags.RUN_FIRST,
                                None,
                                () ),
        'different-review-language-clicked':(GObject.SignalFlags.RUN_FIRST,
                                             None,
                                             (GObject.TYPE_STRING,) ),
    }

    def __init__(self, parent):
        GObject.GObject.__init__(self)
        self.logged_in_person = get_person_from_config()

        self._parent = parent
        # this is a list of review data (softwarecenter.backend.reviews.Review)
        self.reviews = []
        # global review stats, this includes ratings in different languages
        self.global_review_stats = None
        # usefulness stuff
        self.useful_votes = UsefulnessCache()
        self.logged_in_person = None

        label = Gtk.Label()
        label.set_markup(_("Reviews"))
        label.set_padding(6, 6)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)

        self.new_review = Gtk.Button()
        self.new_review.set_label(_("Write your own review"))

        self.header = hb = Gtk.HBox()
        self.header.set_spacing(StockEms.MEDIUM)
        self.pack_start(hb, False, False, 0)
        hb.pack_start(label, False, False, 0)
        hb.pack_end(self.new_review, False, False, 6)

        self.vbox = Gtk.VBox()
        self.vbox.set_spacing(24)
        self.vbox.set_border_width(6)
        self.pack_start(self.vbox, True, True, 0)

        self.new_review.connect('clicked', lambda w: self.emit('new-review'))
        self.show_all()
        return

    def _on_button_new_clicked(self, button):
        self.emit("new-review")
    
    def update_useful_votes(self, my_votes):
        self.useful_votes = my_votes

    def _fill(self):
        """ take the review data object from self.reviews and build the
            UI vbox out of them
        """
        self.logged_in_person = get_person_from_config()
        if self.reviews:
            for r in self.reviews:
                pkgversion = self._parent.app_details.version
                review = UIReview(r, pkgversion, self.logged_in_person, self.useful_votes)
                self.vbox.pack_start(review, True, True, 0)
        return

    def _be_the_first_to_review(self):
        s = _('Be the first to review it')
        self.new_review.set_label(s)
        self.vbox.pack_start(NoReviewYetWriteOne(), True, True, 0)
        self.vbox.show_all()
        return

    def _install_to_review(self):
        s = '<small><b>%s</b></small>' % _("You need to install this app before you can review it")
        self.install_first_label = Gtk.Label(label=s)
        self.install_first_label.set_use_markup(True)
        self.header.pack_end(self.install_first_label, False, False, 2)
        self.install_first_label.show()
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
        msg = _('Only saved reviews can be displayed')
        m = EmbeddedMessage(title, msg, 'network-offline')
        self.vbox.pack_start(m, True, True, 0)
        
    def _clear_vbox(self, vbox):
        children = vbox.get_children()
        for child in children:
            child.destroy()

    # FIXME: instead of clear/add_reviews/configure_reviews_ui we should provide
    #        a single show_reviews(reviews_data_list)
    def configure_reviews_ui(self):
        """ this needs to be called after add_reviews, it will actually
            show the reviews
        """
        #print 'Review count: %s' % len(self.reviews)

        try:
            self.install_first_label.hide()
        except AttributeError:
            pass
        
        self._clear_vbox(self.vbox)

        # network sensitive stuff, only show write_review if connected,
        # add msg about offline cache usage if offline
        is_connected = network_state_is_connected()
        self.new_review.set_sensitive(is_connected)
        if not is_connected:
            self._add_no_network_connection_msg()

        # only show new_review for installed stuff
        is_installed = (self._parent.app_details and
                        self._parent.app_details.pkg_state == PkgStates.INSTALLED)
        if is_installed:
            self.new_review.show()
        else:
            self.new_review.hide()
            self._install_to_review()

        # always hide spinner and call _fill (fine if there is nothing to do)
        self.hide_spinner()
        self._fill()
        self.vbox.show_all()

        if self.reviews:
            # adjust label if we have reviews
            if self._any_reviews_current_user():
                self.new_review.hide()
            else:
                self.new_review.set_label(_("Write your own review"))
        else:
            # no reviews, either offer to write one or show "none"
            if is_installed and is_connected:
                self._be_the_first_to_review()
            else:
                self.vbox.pack_start(NoReviewYet(), True, True, 0)

        # if there are no reviews, try english as fallback
        language = get_language()
        if (len(self.reviews) == 0 and
            self.global_review_stats and
            self.global_review_stats.ratings_total > 0 and
            language != "en"):
            button = Gtk.Button(_("Show reviews in english"))
            button.connect(
                "clicked", self._on_different_review_language_clicked)
            button.show()
            self.vbox.pack_start(button, True, True, 0)                

        # only show the "More" button if there is a chance that there
        # are more
        if self.reviews and len(self.reviews) % REVIEWS_BATCH_PAGE_SIZE == 0:
            button = Gtk.Button(_("Show more reviews"))
            button.connect("clicked", self._on_more_reviews_clicked)
            button.show()
            self.vbox.pack_start(button, True, True, 0)                
        return

    def _on_more_reviews_clicked(self, button):
        # remove buttn and emit signal
        self.vbox.remove(button)
        self.emit("more-reviews-clicked")

    def _on_different_review_language_clicked(self, button):
        language = "en"
        self.vbox.remove(button)
        self.emit("different-review-language-clicked", language)

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
        try:
            self.install_first_label.hide()
        except AttributeError:
            pass
        
        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)

        hb = Gtk.HBox(spacing=12)
        a.add(hb)

        spinner = Gtk.Spinner()
        spinner.start()

        hb.pack_start(spinner, False, False, 0)

        l = Gtk.Label()
        l.set_markup(message)
        l.set_use_markup(True)

        hb.pack_start(l, False, False, 0)

        self.vbox.pack_start(a, False, False, 0)
        self.vbox.show_all()
        return

    def hide_spinner(self):
        for child in self.vbox.get_children():
            if isinstance(child, Gtk.Alignment):
                child.destroy()
        return

    def draw(self, cr, a):
        for r in self.vbox:
            if isinstance(r, (UIReview)):
                r.draw(cr, r.get_allocation())
        return


class UIReview(Gtk.VBox):
    """ the UI for a individual review including all button to mark
        useful/inappropriate etc
    """
    def __init__(self, review_data=None, app_version=None, 
                 logged_in_person=None, useful_votes=None):
        GObject.GObject.__init__(self)
        self.set_spacing(StockEms.LARGE)

        self.header = Gtk.HBox()
        self.header.set_spacing(StockEms.MEDIUM)
        self.body = Gtk.VBox()
        self.footer_split = Gtk.VBox()
        self.footer = Gtk.HBox()

        self.useful = None
        self.yes_like = None
        self.no_like = None
        self.status_box = Gtk.HBox()
        self.submit_error_img = Gtk.Image()
        self.submit_error_img.set_from_stock(
                                Gtk.STOCK_DIALOG_ERROR,
                                Gtk.IconSize.SMALL_TOOLBAR)
        self.submit_status_spinner = Gtk.Spinner()
        self.submit_status_spinner.set_size_request(12,12)
        self.acknowledge_error = Gtk.Button()
        self.acknowledge_error.set_label(_("<small>OK</small>"))
        self.usefulness_error = False

        self.pack_start(self.header, False, False, 0)
        self.pack_start(self.body, False, False, 0)
        self.pack_start(self.footer_split, False, False, 0)
        
        self.logged_in_person = logged_in_person
        self.person = None
        self.id = None
        self.useful_votes = useful_votes

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
            self._build_usefulness_ui(current_user_reviewer, useful_total, useful_favorable, self.useful_votes)
            return
        if type == 'progress':
            self.submit_status_spinner.start()
            self.submit_status_spinner.show()
            self.status_label = Gtk.Label.new("<small><b>%s</b></small>" % _(u"Submitting now\u2026"))
            self.status_box.pack_start(self.submit_status_spinner, False, False, 0)
            self.status_label.set_padding(2,0)
            self.status_box.pack_start(self.status_label, False, False, 0)
            self.status_label.show()
        if type == 'error':
            self.submit_error_img.show()
            self.status_label = Gtk.Label.new("<small><b>%s</b></small>" % _("Error submitting usefulness"))
            self.status_box.pack_start(self.submit_error_img, False, False, 0)
            self.status_label.set_padding(2,0)
            self.status_box.pack_start(self.status_label, False, False, 0)
            self.status_label.show()
            self.acknowledge_error.show()
            self.status_box.pack_start(self.acknowledge_error, False, False, 0)
            self.acknowledge_error.connect('clicked', self._on_error_acknowledged, current_user_reviewer, useful_total, useful_favorable)
        self.status_box.show()
        self.footer.pack_start(self.status_box, False, False, 0)
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

        app_name = review_data.app_name or review_data.package_name
        review_version = review_data.version
        self.useful_total = useful_total = review_data.usefulness_total
        useful_favorable = review_data.usefulness_favorable
        useful_submit_error = review_data.usefulness_submit_error

        dark_color = '#000'
        m = self._whom_when_markup(self.person, displayname, cur_t, dark_color)

        who_when = Gtk.Label()
        who_when.set_markup(m)

        summary = Gtk.Label()
        try:
            summary.set_markup('<b>%s</b>' % GObject.markup_escape_text(review_data.summary))
        except Exception, e:
            print e
            summary.set_text("Error parsing summary")

        summary.set_ellipsize(Pango.EllipsizeMode.END)
        summary.set_selectable(True)
        summary.set_alignment(0, 0.5)

        text = Gtk.Label()
        text.set_text(review_data.review_text)
        text.set_line_wrap(True)
        text.set_selectable(True)
        text.set_alignment(0, 0)

        stars = Star()
        stars.set_rating(review_data.rating)

        self.header.pack_start(stars, False, False, 0)
        self.header.pack_start(summary, False, False, 0)
        self.header.pack_end(who_when, False, False, 0)
        self.body.pack_start(text, False, False, 0)
        
        #if review version is different to version of app being displayed, 
        # alert user
        version_lbl = None
        if (review_version and
            app_version and
            upstream_version_compare(review_version, app_version) != 0):
            version_string = _("This review was written for a different version of %(app_name)s (Version: %(version)s)") % { 
                'app_name' : app_name,
                'version' : GObject.markup_escape_text(upstream_version(review_version))
                }

            m = '<small><i><span color="%s">%s</span></i></small>'
            version_lbl = Gtk.Label(label=m % (dark_color, version_string))
            version_lbl.set_use_markup(True)
            version_lbl.set_padding(0,3)
            version_lbl.set_ellipsize(1)
            version_lbl.set_alignment(0, 0.5)
            self.footer_split.pack_start(version_lbl, False, False, 0)

        self.footer_split.pack_start(self.footer, False, False, 0)

        current_user_reviewer = False
        if self.person == self.logged_in_person:
            current_user_reviewer = True

        self._build_usefulness_ui(current_user_reviewer, useful_total,
                                  useful_favorable, useful_votes, useful_submit_error)

        # Translators: This link is for flagging a review as inappropriate.
        # To minimize repetition, if at all possible, keep it to a single word.
        # If your language has an obvious verb, it won't need a question mark.
        self.complain = Link('<small>%s</small>' % _('Inappropriate?'))
        self.footer.pack_end(self.complain, False, False, 0)
        self.complain.connect('clicked', self._on_report_abuse_clicked)
        # FIXME: dynamically update this on network changes
        self.complain.set_sensitive(network_state_is_connected())
        #~ self.body.connect('size-allocate', self._on_allocate, stars, 
                          #~ summary, text, who_when, version_lbl, self.complain)
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
            self.footer.pack_start(self.useful, False, False, 3)
            # add here, but only populate if its not the own review
            self.likebox = Gtk.HBox()
            if already_voted == None and not current_user_reviewer:
                self.yes_like = Link('<small>%s</small>' % _('Yes'))
                self.no_like = Link('<small>%s</small>' % _('No'))
                self.yes_like.connect('clicked', self._on_useful_clicked, True)
                self.no_like.connect('clicked', self._on_useful_clicked, False)
                self.yes_no_separator = Gtk.Label(label="<small>/</small>")
                self.yes_no_separator.set_use_markup(True)
                self.yes_like.show()
                self.no_like.show()
                self.yes_no_separator.show()
                self.likebox.set_spacing(3)
                self.likebox.pack_start(self.yes_like, False, False, 0)
                self.likebox.pack_start(self.yes_no_separator, False, False, 0)
                self.likebox.pack_start(self.no_like, False, False, 0)
                self.footer.pack_start(self.likebox, False, False, 0)
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
        '''returns Gtk.Label() to be used as usefulness label depending 
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
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful. Did you?",
                    "%(useful_favorable)s of %(useful_total)s people "
                    "found this review helpful. Did you?",
                    useful_total) % { 'useful_total' : useful_total,
                                    'useful_favorable' : useful_favorable,
                                    }
        else:
        #only display these special strings if the user voted either way
            if already_voted:
                if useful_total == 1:
                    s = _("You found this review helpful.")
                else:
                    s = gettext.ngettext(
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful, including you",
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful, including you.",
                        useful_total) % { 'useful_total' : useful_total,
                                    'useful_favorable' : useful_favorable,
                                    }
            else:
                if useful_total == 1:
                    s = _("You found this review unhelpful.")
                else:
                    s = gettext.ngettext(
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful; you did not.",
                        "%(useful_favorable)s of %(useful_total)s people "
                        "found this review helpful; you did not.",
                        useful_total) % { 'useful_total' : useful_total,
                                    'useful_favorable' : useful_favorable,
                                    }
                    
        
        return Gtk.Label(label='<small>%s</small>' % s)

    def _whom_when_markup(self, person, displayname, cur_t, dark_color):
        nice_date = get_nice_date_string(cur_t)
        #dt = datetime.datetime.utcnow() - cur_t

        # prefer displayname if available
        correct_name = displayname or person

        if person == self.logged_in_person:
            m = '<span color="%s"><b>%s (%s)</b>, %s</span>' % (
                dark_color,
                GObject.markup_escape_text(correct_name),
                # TRANSLATORS: displayed in a review after the persons name,
                # e.g. "Wonderful text based app" mvo (that's you) 2011-02-11"
                _("that's you"),
                GObject.markup_escape_text(nice_date))
        else:
            try:
                m = '<span color="%s"><b>%s</b>, %s</span>' % (
                    dark_color,
                    GObject.markup_escape_text(correct_name),
                    GObject.markup_escape_text(nice_date))
            except Exception, e:
                print e
            finally:
                m = "Error parsing name"

        return m

    def draw(self, widget, cr):
        return


class EmbeddedMessage(UIReview):

    def __init__(self, title='', message='', icon_name=''):
        UIReview.__init__(self)
        self.label = None
        self.image = None
        
        a = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        self.body.pack_start(a, False, False, 0)

        hb = Gtk.HBox()
        hb.set_spacing(12)
        a.add(hb)

        if icon_name:
            self.image = Gtk.Image.new_from_icon_name(icon_name,
                                                      Gtk.IconSize.DIALOG)
            hb.pack_start(self.image, False, False, 0)

        self.label = Gtk.Label()
        self.label.set_line_wrap(True)
        self.label.set_alignment(0, 0.5)

        if title:
            self.label.set_markup('<b><big>%s</big></b>\n%s' % (title, message))
        else:
            self.label.set_markup(message)

        hb.pack_start(self.label, True, True, 0)
        self.show_all()
        return

    def draw(self, cr, a):
        cr.save()
        cr.rectangle(a)
        #color = mkit.floats_from_gdkcolor(self.style.mid[self.state])
        #cr.set_source_rgba(*color+(0.2,))
        #cr.fill()
        #cr.restore()


class NoReviewYet(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is not installed """
    def __init__(self, *args, **kwargs):
        # TRANSLATORS: displayed if there are no reviews for the app yet
        #              and the user does not have it installed
        title = _("This app has not been reviewed yet")
        msg = _('You need to install this app before you can review it')
        EmbeddedMessage.__init__(self, title, msg)


class NoReviewYetWriteOne(EmbeddedMessage):
    """ represents if there are no reviews yet and the app is installed """
    def __init__(self, *args, **kwargs):

        # TRANSLATORS: displayed if there are no reviews yet and the user
        #              has the app installed
        title = _('Got an opinion?')
        msg = _('Be the first to contribute a review for this application')

        EmbeddedMessage.__init__(self, title, msg, 'text-editor')
        return



if __name__ == "__main__":
    # FIXME: portme
    #w = StarRatingSelector()
    w = None
    #~ w.set_avg_rating(3.5)
    #~ w.set_nr_reviews(101)

    l = Gtk.Label(label='focus steeler')
    l.set_selectable(True)

    vb = Gtk.VBox(spacing=6)
    vb.pack_start(l, True, True, 0)
    vb.pack_start(w, True, True, 0)

    win = Gtk.Window()
    win.add(vb)
    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    Gtk.main()