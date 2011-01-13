#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2009 Canonical
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
gobject.threads_init()

import datetime
import gtk
import locale
import logging
import os
import pickle
import simplejson
import sys
import tempfile
import time
import threading
import urllib

from gettext import gettext as _
from Queue import Queue
from optparse import OptionParser

from softwarecenter.backend.restfulclient import UbuntuSSOAPI

import piston_mini_client

from softwarecenter.paths import *
from softwarecenter.enums import MISSING_APP_ICON
from softwarecenter.backend.login_sso import LoginBackendDbusSSO
from softwarecenter.db.database import Application
from softwarecenter.db.reviews import Review
from softwarecenter.utils import *
from softwarecenter.SimpleGtkbuilderApp import SimpleGtkbuilderApp
from softwarecenter.distro import get_distro
from softwarecenter.view.widgets.reviews import StarRatingSelector, StarCaption
from softwarecenter.gwibber_helper import GwibberHelper

from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI, ReviewRequest

#import httplib2
#httplib2.debuglevel = 1

# get current distro and set default server root
distro = get_distro()
SERVER_ROOT=distro.REVIEWS_SERVER

# the SUBMIT url
SUBMIT_POST_URL = SERVER_ROOT+"/reviews/en/ubuntu/lucid/+create"
# the REPORT url
REPORT_POST_URL = SERVER_ROOT+"/reviews/%s/+report-review"
# server status URL
SERVER_STATUS_URL = SERVER_ROOT+"/reviews/+server-status"

class UserCancelException(Exception):
    """ user pressed cancel """
    pass

TRANSMIT_STATE_NONE="transmit-state-none"
TRANSMIT_STATE_INPROGRESS="transmit-state-inprogress"
TRANSMIT_STATE_DONE="transmit-state-done"
TRANSMIT_STATE_ERROR="transmit-state-error"

class GRatingsAndReviews(gobject.GObject):
    """ Access ratings&reviews API as a gobject """

    __gsignals__ = {
        # send when a transmit is started
        "transmit-start" : (gobject.SIGNAL_RUN_LAST,
                            gobject.TYPE_NONE, 
                            (gobject.TYPE_PYOBJECT, ),
                            ),
        # send when a transmit was successful
        "transmit-success" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT, ),
                              ),
        # send when a transmit failed
        "transmit-failure" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT, str),
                              ),
    }

    def __init__(self, token):
        super(GRatingsAndReviews, self).__init__()
        # piston worker thread
        self.worker_thread = Worker(token)
        self.worker_thread.start()
        glib.timeout_add(500, self._check_thread_status)
    def submit_review(self, review):
        self.emit("transmit-start", review)
        self.worker_thread.pending_reviews.put(review)
    def report_abuse(self, review_id, summary, text):
        self.emit("transmit-start", review_id)
        self.worker_thread.pending_reports.put((int(review_id), summary, text))
    def server_status(self):
        self.worker_thread.pending_server_status()
    def shutdown(self):
        self.worker_thread.shutdown()
    # internal
    def _check_thread_status(self):
        if self.worker_thread._transmit_state == TRANSMIT_STATE_DONE:
            self.emit("transmit-success", "")
            self.worker_thread._transmit_state = TRANSMIT_STATE_NONE
        elif self.worker_thread._transmit_state == TRANSMIT_STATE_ERROR:
            self.emit("transmit-failure", "", 
                      self.worker_thread._transmit_error_str)
            self.worker_thread._transmit_state = TRANSMIT_STATE_NONE
        return True

class Worker(threading.Thread):

    def __init__(self, token):
        # init parent
        threading.Thread.__init__(self)
        self.pending_reviews = Queue()
        self.pending_reports = Queue()
        self.pending_server_status = Queue()
        self._shutdown = False
        # FIXME: instead of a binary value we need the state associated
        #        with each request from the queue
        self._transmit_state = TRANSMIT_STATE_NONE
        self._transmit_error_str = ""
        self.display_name = "No display name"
        auth = piston_mini_client.auth.OAuthAuthorizer(token["token"],
                                                       token["token_secret"],
                                                       token["consumer_key"],
                                                       token["consumer_secret"])
        # change default server to the SSL one
        distro = get_distro()
        service_root = distro.REVIEWS_SERVER_SSL
        self.rnrclient = RatingsAndReviewsAPI(service_root=service_root,
                                              auth=auth)

    def run(self):
        """Main thread run interface, logs into launchpad and waits
           for commands
        """
        logging.debug("worker thread run")
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            #logging.debug("worker: _wait_for_commands")
            self._submit_reviews_if_pending()
            self._submit_reports_if_pending()
            time.sleep(0.2)
            if (self._shutdown and
                self.pending_reviews.empty() and
                self.pending_reports.empty()):
                return

    # reports
    def queue_report(self, report):
        """ queue a new report for sending to LP """
        logging.debug("queue_report %s %s %s" % report)
        self.pending_reports.put(report)

    def _submit_reports_if_pending(self):
        """ the actual report function """
        while not self.pending_reports.empty():
            logging.debug("POST report")
            self._transmit_state = TRANSMIT_STATE_INPROGRESS
            (review_id, summary, text) = self.pending_reports.get()
            try:
                res = self.rnrclient.flag_review(review_id=review_id,
                                                 reason=summary,
                                                 text=text)
                self._transmit_state = TRANSMIT_STATE_DONE
                sys.stdout.write(simplejson.dumps(res))
            except Exception as e:
                logging.exception("flag_review failed")
                self._write_exception_html_log_if_needed(e)
                self._transmit_state = TRANSMIT_STATE_ERROR
                self._transmit_error_str = _("Failed to submit report")
            self.pending_reports.task_done()

    def _write_exception_html_log_if_needed(self, e):
        # write out a "oops.html" 
        if type(e) is piston_mini_client.APIError:
            f=tempfile.NamedTemporaryFile(
                prefix="sc_submit_oops_", suffix=".html", delete=False)
            # new piston-mini-client has only the body of the returned data
            # older just pushes it into a big string
            if hasattr(e, "body") and e.body:
                f.write(e.body)
            else:
                f.write(str(e))

    # reviews
    def queue_review(self, review):
        """ queue a new review for sending to LP """
        logging.debug("queue_review %s" % review)
        self.pending_reviews.put(review)

    def _submit_reviews_if_pending(self):
        """ the actual submit function """
        while not self.pending_reviews.empty():
            logging.debug("_submit_review")
            self._transmit_state = TRANSMIT_STATE_INPROGRESS
            review = self.pending_reviews.get()
            piston_review = ReviewRequest()
            piston_review.package_name = review.app.pkgname
            piston_review.app_name = review.app.appname
            piston_review.summary = review.summary
            piston_review.version = review.package_version
            piston_review.review_text = review.text
            piston_review.date = str(review.date)
            piston_review.rating = review.rating
            piston_review.language = review.language
            piston_review.arch_tag = get_current_arch()
            #FIXME: not hardcode
            piston_review.origin = "ubuntu"
            piston_review.distroseries=distro.get_codename()
            try:
                res = self.rnrclient.submit_review(review=piston_review)
                self._transmit_state = TRANSMIT_STATE_DONE
                # output the resulting json so that the parent can read it
                sys.stdout.write(simplejson.dumps(res))
            except Exception as e:
                logging.exception("submit_review")
                self._write_exception_html_log_if_needed(e)
                self._transmit_state = TRANSMIT_STATE_ERROR
                self._transmit_error_str = _("Failed to submit review")
            self._transmit_state
            self.pending_reviews.task_done()

    def verify_server_status(self):
        """ verify that the server we want to talk to can be reached
            this method should be overriden if clients talk to a different
            server than rnr
        """
        try:
            resp = urllib.urlopen(SERVER_STATUS_URL).read()
            if resp != "ok":
                return False
        except Exception, e:
            logging.error("exception from '%s': '%s'" % (SERVER_STATUS_URL, e))
            return False
        return True


class BaseApp(SimpleGtkbuilderApp):

    def __init__(self, datadir, uifile):
        SimpleGtkbuilderApp.__init__(
            self, os.path.join(datadir,"ui",uifile), "software-center")
        self.appname = _("Ubuntu Software Center")
        self.token = None
        self.display_name = None
        self._login_successful = False
        self._whoami_token_reset_nr = 0
        # status spinner
        self.status_spinner = gtk.Spinner()
        self.status_spinner.set_size_request(32,32)
        self.login_spinner_vbox.pack_start(self.status_spinner, False)
        self.login_spinner_vbox.reorder_child(self.status_spinner, 0)
        self.status_spinner.show()
        #submit status spinner
        self.submit_spinner = gtk.Spinner()
        self.submit_spinner.set_size_request(*gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR))
        #submit error image
        self.submit_error_img = gtk.Image()
        self.submit_error_img.set_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_SMALL_TOOLBAR)
        #label size to prevent image or spinner from resizing
        self.label_transmit_status.set_size_request(-1, gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)[1])

    def run(self):
        # initially display a 'Connecting...' page
        self.main_notebook.set_current_page(0)
        self.login_status_label.set_markup('<b><big>%s</big></b>' % _("Signing In"))
        self.status_spinner.start()
        self.submit_window.show()
        # now run the loop
        self.login()

    def quit(self):
        sys.exit(0)

    def _add_spellcheck_to_textview(self, textview):
        """ adds a spellchecker (if available) to the given gtk.textview """
        try:
            import gtkspell
            # mvo: gtkspell.get_from_text_view() is broken, so we use this
            #      method instead, the second argument is the language to
            #      use (that is directly passed to pspell)
            spell = gtkspell.Spell(textview, None)
        except ImportError:
            return None
        return spell

    def login(self, show_register=True):
        login_text = _("To review software or to report abuse you need to "
                       "sign in to a Ubuntu Single Sign-On account.")
        self.sso = LoginBackendDbusSSO(self.submit_window.window.xid, 
                                       self.appname, login_text)
        self.sso.connect("login-successful", self._maybe_login_successful)
        self.sso.connect("login-canceled", self._login_canceled)
        if show_register:
            self.sso.login_or_register()
        else:
            self.sso.login()

    def _login_canceled(self, sso):
        self.status_spinner.hide()
        self.login_status_label.set_markup('<b><big>%s</big></b>' % _("Login was canceled"))

    def _maybe_login_successful(self, sso, oauth_result):
        """ called after we have the token, then we go and figure out our name """
        self.token = oauth_result
        self.ssoapi = UbuntuSSOAPI(self.token)
        self.ssoapi.connect("whoami", self._whoami_done)
        self.ssoapi.connect("error", self._whoami_error)
        self.ssoapi.whoami()

    def _whoami_done(self, ssologin, result):
        self.display_name = result["displayname"]
        self._create_gratings_api()
        self.login_successful(self.display_name)

    def _whoami_error(self, ssologin, e):
        logging.error("whoami error '%s'" % e)
        # HACK: clear the token from the keyring assuming that it expired
        #       or got deauthorized by the user on the website
        # this really should be done by ubuntu-sso-client itself
        import lazr.restfulclient.errors
        # compat  with maverick, it does not have Unauthorized yet
        if hasattr(lazr.restfulclient.errors, "Unauthorized"):
            errortype = lazr.restfulclient.errors.Unauthorized
        else:
            errortype = lazr.restfulclient.errors.HTTPError
        if (type(e) == errortype and
            self._whoami_token_reset_nr == 0):
            logging.warn("authentication error, reseting token and retrying")
            clear_token_from_ubuntu_sso(self.appname)
            self._whoami_token_reset_nr += 1
            self.login(show_register=False)
            return
        # show error
        self.status_spinner.hide()
        self.login_status_label.set_markup('<b><big>%s</big></b>' % _("Failed to log in"))

    def login_successful(self, display_name):
        """ callback when the login was successful """
        pass

    def on_button_cancel_clicked(self, button=None):
        # bring it down gracefully
        if hasattr(self, "api"):
            self.api.shutdown()
        while gtk.events_pending():
            gtk.main_iteration()
        self.quit()

    def _create_gratings_api(self):
        self.api = GRatingsAndReviews(self.token)
        self.api.connect("transmit-start", self.on_transmit_start)
        self.api.connect("transmit-success", self.on_transmit_success)
        self.api.connect("transmit-failure", self.on_transmit_failure)

    def on_transmit_start(self, api, trans):
        self.button_post.set_sensitive(False)
        self.button_cancel.set_sensitive(False)
        if self._clear_status_imagery():
            self.status_hbox.pack_start(self.submit_spinner, False)
            self.status_hbox.reorder_child(self.submit_spinner, 0)
            self.submit_spinner.show()
            self.submit_spinner.start()
            self.label_transmit_status.set_text(self.SUBMIT_MESSAGE)

    def on_transmit_success(self, api, trans):
        self.api.shutdown()
        self.quit()

    def on_transmit_failure(self, api, trans, error):
        if self._clear_status_imagery():
            self.status_hbox.pack_start(self.submit_error_img, False)
            self.status_hbox.reorder_child(self.submit_error_img, 0)
            self.submit_error_img.show()
            self.label_transmit_status.set_text(error)
            self.button_post.set_sensitive(True)
            self.button_cancel.set_sensitive(True)

    def _clear_status_imagery(self):
        #clears spinner or error image from dialog submission label before trying to display one or the other
        try: 
            result = self.status_hbox.query_child_packing(self.submit_spinner)
            self.status_hbox.remove(self.submit_spinner)
        except TypeError:
            pass
        
        try: 
            result = self.status_hbox.query_child_packing(self.submit_error_img)
            self.status_hbox.remove(self.submit_error_img)
        except TypeError:
            pass
        
        return True
        
            
            

class SubmitReviewsApp(BaseApp):
    """ review a given application or package """


    STAR_SIZE = (32, 32)
    APP_ICON_SIZE = 48
    #character limits for text boxes and hurdles for indicator changes 
    #   (overall field maximum, limit to display warning, limit to change colour)
    SUMMARY_CHAR_LIMITS = (80, 60, 70)
    REVIEW_CHAR_LIMITS = (5000, 4900, 4950)
    #alert colours for character warning labels
    NORMAL_COLOUR = "000000"
    ERROR_COLOUR = "FF0000"
    SUBMIT_MESSAGE = _("Submitting Review")
    

    def __init__(self, app, version, iconname, parent_xid, datadir):
        BaseApp.__init__(self, datadir, "submit_review.ui")

        # legal fineprint, do not change without consulting a lawyer
        msg = _("By submitting this review, you agree not to include anything defamatory, infringing, or illegal. Canonical may, at its discretion, publish your name and review in Ubuntu Software Center and elsewhere, and allow the software or content author to publish it too.")
        self.label_legal_fineprint.set_markup('<span size="x-small">%s</span>' % msg)

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path("/usr/share/app-install/icons/")
        self.submit_window.connect("destroy", self.on_button_cancel_clicked)
        self._add_spellcheck_to_textview(self.textview_review)

        # interactive star rating
        self.star_rating = StarRatingSelector(0, star_size=self.STAR_SIZE)
        self.star_caption = StarCaption()

        self.star_rating.set_caption_widget(self.star_caption)
        self.star_rating.set_padding(3, 3, 3, 0)
        self.star_caption.show()

        self.rating_hbox.pack_start(self.star_rating, False)
        self.rating_hbox.reorder_child(self.star_rating, 0)
        self.rating_hbox.pack_start(self.star_caption, False, False)
        self.rating_hbox.reorder_child(self.star_caption, 1)

        self.review_buffer = self.textview_review.get_buffer()

        # data
        self.app = app
        self.version = version
        self.iconname = iconname
        
        # title
        self.submit_window.set_title(_("Review %s" % self.app.name))

        # gwibber accounts
        self.gwibber_accounts = []

        self.review_summary_entry.connect('changed', self._on_mandatory_text_entry_changed)
        self.star_rating.connect('changed', self._on_mandatory_fields_changed)
        self.review_buffer.connect('changed', self._on_text_entry_changed)
        

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.submit_window.realize()
                self.submit_window.window.set_transient_for(win)

        self.submit_window.set_position(gtk.WIN_POS_MOUSE)

    def _setup_details(self, widget, app, iconname, version, display_name):
        # icon shazam
        if iconname:
            icon = None
            try:
                icon = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
            except:
                pass

            if not icon:
                icon = self.icons.load_icon(MISSING_APP_ICON,
                                            self.APP_ICON_SIZE, 0)

            self.review_appicon.set_from_pixbuf(icon)

        # dark color
        dark = widget.style.dark[0].to_string()

        # title
        m = '<b><span size="x-large">%s</span></b>\n%s %s'
        self.review_title.set_markup(m % (app.name, _('Reviewed by'), display_name))

        # review label
        self.review_label.set_markup('<b><span color="%s">%s</span></b>' % (dark, _('Review')))

        # review summary label
        self.review_summary_label.set_markup('<b><span color="%s">%s</span></b>' % (dark, _('Summary')))
        
        #rating label
        self.rating_label.set_markup('<b><span color="%s">%s</span></b>' % (dark, _('Rating')))
        
        self._setup_gwibber_gui()
        
        return

    def _on_mandatory_fields_changed(self, widget):
        self._enable_or_disable_post_button()
    
    def _on_mandatory_text_entry_changed(self, widget):
        self._check_summary_character_count()
        self._on_mandatory_fields_changed(widget)
    
    def _on_text_entry_changed(self, widget):
        self._check_review_character_count()
        self._on_mandatory_fields_changed(widget)
        
    def _enable_or_disable_post_button(self):
        summary_chars = self.review_summary_entry.get_text_length()
        review_chars = self.review_buffer.get_char_count()
        if (summary_chars and summary_chars <= self.SUMMARY_CHAR_LIMITS[0] and
            review_chars and review_chars <= self.REVIEW_CHAR_LIMITS[0] and
            self.star_rating.get_rating()):
            self.button_post.set_sensitive(True)
        else:
            self.button_post.set_sensitive(False)
    
    def _check_summary_character_count(self):
        summary_chars = self.review_summary_entry.get_text_length()
        if summary_chars > self.SUMMARY_CHAR_LIMITS[1] - 1:
            markup = self._get_fade_colour_markup(
                self.NORMAL_COLOUR, self.ERROR_COLOUR, 
                self.SUMMARY_CHAR_LIMITS[2], self.SUMMARY_CHAR_LIMITS[0], 
                summary_chars)
            self.summary_char_label.set_markup(markup)
        else:
            self.summary_char_label.set_text('')
    
    def _check_review_character_count(self): 
        review_chars = self.review_buffer.get_char_count()
        if review_chars > self.REVIEW_CHAR_LIMITS[1] - 1:
            markup = self._get_fade_colour_markup(
                self.NORMAL_COLOUR, self.ERROR_COLOUR, 
                self.REVIEW_CHAR_LIMITS[2], self.REVIEW_CHAR_LIMITS[0], 
                review_chars) 
            self.review_char_label.set_markup(markup)
        else:
            self.review_char_label.set_text('')
        
    def _get_fade_colour_markup(self, full_col, empty_col, cmin, cmax, curr):
        """takes two colours as well as a minimum and maximum value then
           fades one colour into the other based on the proportion of the
           current value between the min and max
           returns a pango color string
        """
        markup = '<span fgcolor="#%s">%s</span>'
        if curr > cmax:
            return markup % (empty_col, str(cmax-curr))
        elif curr < cmin:
            return markup % (full_col, str(cmax-curr))
        elif cmax == cmin:  #saves division by 0 later if same value was passed as min and max
            return markup % (full_col, str(cmax-curr))
        else:
            #distance between min and max values to fade colours
            scale = cmax - cmin
            #percentage to fade colour by, based on current number of chars
            percentage = (curr - cmin) / float(scale)
            
            full_rgb = self._convert_html_to_rgb(full_col)
            empty_rgb = self._convert_html_to_rgb(empty_col)
            
            #calc changes to each of the r g b values to get the faded colour
            red_change = full_rgb[0] - empty_rgb[0]
            green_change = full_rgb[1] - empty_rgb[1]
            blue_change = full_rgb[2] - empty_rgb[2]
            
            new_red = int(full_rgb[0] - (percentage * red_change))
            new_green = int(full_rgb[1] - (percentage * green_change))
            new_blue = int(full_rgb[2] - (percentage * blue_change))

            return_color = self._convert_rgb_to_html(new_red, new_green, new_blue)
            
            return markup % (return_color, str(cmax-curr))
    
    def _convert_html_to_rgb(self, html):
        r = html[0:2]
        g = html[2:4]
        b = html[4:6]
        return (int(r,16), int(g,16), int(b,16))
    
    def _convert_rgb_to_html(self, r, g, b):
        return "%s%s%s" % ("%02X" % r,
                           "%02X" % g,
                           "%02X" % b)

    def on_button_post_clicked(self, button):
        logging.debug("enter_review ok button")
        review = Review(self.app)
        text_buffer = self.textview_review.get_buffer()
        review.text = text_buffer.get_text(text_buffer.get_start_iter(),
                                           text_buffer.get_end_iter())
        review.summary = self.review_summary_entry.get_text()
        review.date = datetime.datetime.now()
        review.language = get_language()
        review.rating = self.star_rating.get_rating()
        review.package_version = self.version
        self.api.submit_review(review)

    def login_successful(self, display_name):
        self.main_notebook.set_current_page(1)
        self._setup_details(self.submit_window, self.app, self.iconname, self.version, display_name)
        return
    
    def _get_gwibber_accounts(self):
        '''calls gwibber helper and gets a list of dicts, each referring to a gwibber account enabled for sending'''
        gh = GwibberHelper()
        self.gwibber_accounts = gh.accounts()
        
        #hardcodes for GUI testing below
        #comment above two lines and uncomment one of the three following lines to test scenario (no accounts / 1 account / 2+ accounts)
        #self.gwibber_accounts = []
        #self.gwibber_accounts = [{u'username': u'jsmith98761', u'user_id': u'235037074', u'service': u'twitter', u'secret_token': u':KEYRING:5', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'235037074-jkldsfjlksdfjklsfdkljfsdjklfdsklj', u'send_enabled': True, u'id': u'600e12c61a2111e095e90015af8bddb6'}]
        #self.gwibber_accounts = [{u'username': u'jsmith98761', u'user_id': u'235037074', u'service': u'twitter', u'secret_token': u':KEYRING:5', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'235037074-safdjkdsfjlksdfjlksdfjlkdsfjklfds', u'send_enabled': True, u'id': u'600e12c61a2111e095e90015af8bddb6'}, {u'username': u'mpt', u'user_id': u'235037075', u'service': u'twitter', u'secret_token': u':KEYRING:5', u'color': u'#729FCF', u'receive_enabled': True, u'access_token': u'235037074-TwSWCsdfjklsdfjksdfjkdsfjkmMCpK', u'send_enabled': True, u'id': u'600e12c61a2111e095e90015af8bddb6'}]
    
        return True
    
    def _setup_gwibber_gui(self):
        if self._get_gwibber_accounts():
            list_length = len(self.gwibber_accounts)
        
            if list_length == 0:
                self._on_no_gwibber_accounts()
            elif list_length == 1:
                self._on_one_gwibber_account()
            else:
                self._on_multiple_gwibber_accounts()
    
    def _on_no_gwibber_accounts(self):
        self.gwibber_hbox.hide()
        self.gwibber_checkbutton.set_active(False)
    
    def _on_one_gwibber_account(self):
        account = self.gwibber_accounts[0]
        acct_text = str.capitalize(str(account['service'])) + " (@" + str(account['username']) + ")"
        self.gwibber_hbox.show()
        gwibber_label = gtk.Label(acct_text)
        self.gwibber_hbox.pack_start(gwibber_label, False)
        self.gwibber_hbox.reorder_child(gwibber_label, 1)
        gwibber_label.show()
    
    def _on_multiple_gwibber_accounts(self):
        self.gwibber_hbox.show()
        gwibber_combo = gtk.combo_box_new_text()

        for account in self.gwibber_accounts:
            acct_text = str.capitalize(str(account['service'])) + " (@" + str(account['username']) + ")"
            gwibber_combo.append_text(acct_text)
        
        gwibber_combo.set_active(0)
        self.gwibber_hbox.pack_start(gwibber_combo, False)
        self.gwibber_hbox.reorder_child(gwibber_combo, 1)
        gwibber_combo.show()


class ReportReviewApp(BaseApp):
    """ report a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"

    APP_ICON_SIZE = 48
    
    SUBMIT_MESSAGE = _("Sending Report")

    def __init__(self, review_id, parent_xid, datadir):
        BaseApp.__init__(self, datadir, "report_abuse.ui")
        # status
        self._add_spellcheck_to_textview(self.textview_report)

        ## make button sensitive when textview has content
        self.textview_report.get_buffer().connect(
            "changed", self._enable_or_disable_report_button)

        # data
        self.review_id = review_id

        # title
        self.submit_window.set_title(_("Report an infringment"))

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.submit_window.realize()
                self.submit_window.window.set_transient_for(win)
        # mousepos
        self.submit_window.set_position(gtk.WIN_POS_MOUSE)
        # simple APIs ftw!
        self.combobox_report_summary = gtk.combo_box_new_text()
        self.report_body_vbox.pack_start(self.combobox_report_summary, False)
        self.report_body_vbox.reorder_child(self.combobox_report_summary, 2)
        self.combobox_report_summary.show()
        for term in [ _("Unspecified"), 
                      _("Offensive language"), 
                      _("Infringes copyright"), 
                      _("Contains inaccuracies"),
                      _("Other") ]:
            self.combobox_report_summary.append_text(term)
        self.combobox_report_summary.set_active(0)

    def _enable_or_disable_report_button(self, buf):
        if buf.get_char_count() > 0:
            self.button_post.set_sensitive(True)
        else:
            self.button_post.set_sensitive(False)

    def _setup_details(self, widget, display_name):
        # dark color
        dark = widget.style.dark[0].to_string()

        # title
        m = '<b><span size="x-large">%s</span></b>\n%s %s'
        self.report_title.set_markup(m % (_('Review Infringment'), _('Reported by'), display_name))

        # report label
        self.report_label.set_markup('<b><span color="%s">%s</span></b>' % (dark, _('Please give details:')))

        # review summary label
        self.report_summary_label.set_markup('<b><span color="%s">%s</span></b>' % (dark, _('Why is this review inappropriate?')))
        return

    def on_button_post_clicked(self, button):
        logging.debug("report_abuse ok button")
        report_summary = self.combobox_report_summary.get_active_text()
        text_buffer = self.textview_report.get_buffer()
        report_text = text_buffer.get_text(text_buffer.get_start_iter(),
                                           text_buffer.get_end_iter())
        self.api.report_abuse(self.review_id, report_summary, report_text)

    def login_successful(self, display_name):
        self.main_notebook.set_current_page(1)
        #self.label_reporter.set_text(display_name)
        self._setup_details(self.submit_window, display_name)
    
if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")

    if os.path.exists("./data/ui/reviews.ui"):
        default_datadir = "./data"
    else:
        default_datadir = "/usr/share/software-center/"

    # common options for optparse go here
    parser = OptionParser()
    parser.add_option("", "--datadir", default=default_datadir)



    # run review personality
    if "submit_review" in sys.argv[0]:
        # check options
        parser.add_option("-a", "--appname")
        parser.add_option("-p", "--pkgname")
        parser.add_option("-i", "--iconname")
        parser.add_option("-V", "--version")
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        if not (options.pkgname and options.version):
            parser.error(_("Missing arguments"))
    
        if options.debug:
            logging.basicConfig(level=logging.DEBUG)                        

        # personality
        logging.debug("submit_review mode")

        # initialize and run
        theapp = Application(options.appname, options.pkgname)
        review_app = SubmitReviewsApp(datadir=options.datadir,
                                      app=theapp, 
                                      parent_xid=options.parent_xid,
                                      iconname=options.iconname,
                                      version=options.version)
        review_app.run()


    # run "report" personality
    if "report_review" in sys.argv[0]:
        # check options
        parser.add_option("", "--review-id") 
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--debug",
                          action="store_true", default=False)
        (options, args) = parser.parse_args()

        if not (options.review_id):
            parser.error(_("Missing review-id arguments"))
    
        if options.debug:
            logging.basicConfig(level=logging.DEBUG)                        

        # personality
        logging.debug("report_abuse mode")

        # initialize and run
        report_app = ReportReviewApp(datadir=options.datadir,
                                      review_id=options.review_id, 
                                      parent_xid=options.parent_xid)
        report_app.run()

    # main
    gtk.main()
