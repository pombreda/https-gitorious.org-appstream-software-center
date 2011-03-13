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
import pango

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
from softwarecenter.config import get_config
from softwarecenter.backend.login_sso import LoginBackendDbusSSO
from softwarecenter.db.database import Application
from softwarecenter.db.reviews import Review
from softwarecenter.utils import *
from softwarecenter.SimpleGtkbuilderApp import SimpleGtkbuilderApp
from softwarecenter.view.dialogs import SimpleGtkbuilderDialog
from softwarecenter.distro import get_distro
from softwarecenter.view.widgets.reviews import StarRatingSelector, StarCaption
from softwarecenter.gwibber_helper import GwibberHelper, GwibberHelperMock

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
    def submit_usefulness(self, review_id, is_useful):
        self.emit("transmit-start", review_id)
        self.worker_thread.pending_usefulness.put((int(review_id), is_useful))
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
        self.pending_usefulness = Queue()
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
            self._submit_usefulness_if_pending()
            time.sleep(0.2)
            if (self._shutdown and
                self.pending_reviews.empty() and
                self.pending_usefulness.empty() and
                self.pending_reports.empty()):
                return

    # usefulness
    def queue_usefulness(self, usefulness):
        """ queue a new usefulness report for sending to LP """
        logging.debug("queue_usefulness %s %s %s" % usefulness)
        self.pending_usefulness.put(usefulness)

    def _submit_usefulness_if_pending(self):
        """ the actual usefulness function """
        while not self.pending_usefulness.empty():
            logging.debug("POST usefulness")
            self._transmit_state = TRANSMIT_STATE_INPROGRESS
            (review_id, is_useful) = self.pending_usefulness.get()
            try:
                res = self.rnrclient.submit_usefulness(
                    review_id=review_id, useful=str(is_useful))
                self._transmit_state = TRANSMIT_STATE_DONE
                sys.stdout.write(simplejson.dumps(res))
            except Exception as e:
                logging.exception("submit_usefulness failed")
                self._write_exception_html_log_if_needed(e)
                self._transmit_state = TRANSMIT_STATE_ERROR
                self._transmit_error_str = _("Failed to submit usefulness")
            self.pending_usefulness.task_done()

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
            piston_review.origin = review.origin
            piston_review.distroseries=distro.get_codename()
            try:
                res = self.rnrclient.submit_review(review=piston_review)
                self._transmit_state = TRANSMIT_STATE_DONE
                # output the resulting ReviewDetails object as json so
                # that the parent can read it
                sys.stdout.write(simplejson.dumps(vars(res)))
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
        # generic data
        self.appname = _("Ubuntu Software Center")
        self.token = None
        self.display_name = None
        self._login_successful = False
        self._whoami_token_reset_nr = 0
        #persistent config
        configfile = os.path.join(
            SOFTWARE_CENTER_CONFIG_DIR, "submit_reviews.cfg")
        self.config = get_config(configfile)
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
        #submit success image
        self.submit_success_img = gtk.Image()
        self.submit_success_img.set_from_stock(gtk.STOCK_APPLY,  gtk.ICON_SIZE_SMALL_TOOLBAR)
        #label size to prevent image or spinner from resizing
        self.label_transmit_status.set_size_request(-1, gtk.icon_size_lookup(gtk.ICON_SIZE_SMALL_TOOLBAR)[1])

    def _get_parent_xid_for_login_window(self):
        return self.submit_window.window.xid

    def run(self):
        # initially display a 'Connecting...' page
        self.main_notebook.set_current_page(0)
        self.login_status_label.set_markup(_(u"Signing in\u2026"))
        self.status_spinner.start()
        self.submit_window.show()
        # now run the loop
        self.login()

    def quit(self, exitcode=0):
        sys.exit(exitcode)

    def _add_spellcheck_to_textview(self, textview):
        """ adds a spellchecker (if available) to the given gtk.textview """
        try:
            import gtkspell
            # mvo: gtkspell.get_from_text_view() is broken, so we use this
            #      method instead, the second argument is the language to
            #      use (that is directly passed to pspell)
            spell = gtkspell.Spell(textview, None)
        except:
            return None
        return spell

    def login(self, show_register=True):
        # either
        login_window_xid = self._get_parent_xid_for_login_window()
        login_text = _("To review software or to report abuse you need to "
                       "sign in to a Ubuntu Single Sign-On account.")
        self.sso = LoginBackendDbusSSO(login_window_xid,
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
        self.quit(1)

    def _create_gratings_api(self):
        self.api = GRatingsAndReviews(self.token)
        self.api.connect("transmit-start", self.on_transmit_start)
        self.api.connect("transmit-success", self.on_transmit_success)
        self.api.connect("transmit-failure", self.on_transmit_failure)

    def on_transmit_start(self, api, trans):
        self.button_post.set_sensitive(False)
        self.button_cancel.set_sensitive(False)
        self._change_status("progress",  self.SUBMIT_MESSAGE)

    def on_transmit_success(self, api, trans):
        self.api.shutdown()
        self.quit()

    def on_transmit_failure(self, api, trans, error):
        self._change_status("fail",  error)
        self.button_post.set_sensitive(True)
        self.button_cancel.set_sensitive(True)
            
    def _change_status(self, type,  message):
        """method to separate the updating of status icon/spinner and message in the submit review window,
         takes a type (progress, fail, success) as a string and a message string then updates status area accordingly"""
        self._clear_status_imagery()
        if type == "progress":
            self.status_hbox.pack_start(self.submit_spinner, False)
            self.status_hbox.reorder_child(self.submit_spinner, 0)
            self.submit_spinner.show()
            self.submit_spinner.start()
            self.label_transmit_status.set_text(message)
        elif type == "fail":
            self.status_hbox.pack_start(self.submit_error_img, False)
            self.status_hbox.reorder_child(self.submit_error_img, 0)
            self.submit_error_img.show()
            self.label_transmit_status.set_text(message)
        elif type == "success":
            self.status_hbox.pack_start(self.submit_success_img, False)
            self.status_hbox.reorder_child(self.submit_success_img, 0)
            self.submit_success_img.show()
            self.label_transmit_status.set_text(message)

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
            
         try: 
            result = self.status_hbox.query_child_packing(self.submit_success_img)
            self.status_hbox.remove(self.submit_success_img)
         except TypeError:
            pass
        
         return
        
            
            

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
    

    def __init__(self, app, version, iconname, origin, parent_xid, datadir):
        BaseApp.__init__(self, datadir, "submit_review.ui")
        self.datadir = datadir
        # legal fineprint, do not change without consulting a lawyer
        msg = _("By submitting this review, you agree not to include anything defamatory, infringing, or illegal. Canonical may, at its discretion, publish your name and review in Ubuntu Software Center and elsewhere, and allow the software or content author to publish it too.")
        self.label_legal_fineprint.set_markup('<span size="x-small">%s</span>' % msg)

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path("/usr/share/app-install/icons/")
        self.submit_window.connect("destroy", self.on_button_cancel_clicked)
        self._add_spellcheck_to_textview(self.textview_review)

        # gwibber stuff
        self.gwibber_combo = gtk.combo_box_new_text()
        #cells = self.gwibber_combo.get_cells()
        #cells[0].set_property("ellipsize", pango.ELLIPSIZE_END)
        self.gwibber_hbox.pack_start(self.gwibber_combo, True)
        if "SOFTWARE_CENTER_GWIBBER_MOCK_USERS" in os.environ:
            self.gwibber_helper = GwibberHelperMock()
        else:
            self.gwibber_helper = GwibberHelper()
        
        #get a dict with a saved gwibber_send (boolean) and gwibber account_id for persistent state
        self.gwibber_prefs = self._get_gwibber_prefs()

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
        self.origin = origin
        self.iconname = iconname
        
        # title
        self.submit_window.set_title(_("Review %s" % self.app.name))

        self.review_summary_entry.connect('changed', self._on_mandatory_text_entry_changed)
        self.star_rating.connect('changed', self._on_mandatory_fields_changed)
        self.review_buffer.connect('changed', self._on_text_entry_changed)
        
        # gwibber stuff
        self._setup_gwibber_gui()

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.submit_window.realize()
                self.submit_window.window.set_transient_for(win)

        self.submit_window.set_position(gtk.WIN_POS_MOUSE)

    def _setup_details(self, widget, app, iconname, version, display_name):
        # icon shazam
        try:
            icon = self.icons.load_icon(iconname, self.APP_ICON_SIZE, 0)
        except:
            icon = self.icons.load_icon(MISSING_APP_ICON, self.APP_ICON_SIZE, 0)
        self.review_appicon.set_from_pixbuf(icon)

        # title
        m = '<b><span size="x-large">%s</span></b>\n%s'
        self.review_title.set_markup(m % (app.name, version))

        # review label
        self.review_label.set_markup(_('Review by: %s') % display_name)

        # review summary label
        self.review_summary_label.set_markup(_('Summary:'))
        
        #rating label
        self.rating_label.set_markup(_('Rating:'))
        return

    # force resize of the legal label when the app resizes, if not
    # done it looks really bad, thanks gtk for not doing this for me
    def on_submit_window_size_allocate(self, *args):
        self._resize_legal_label()
    def on_submit_window_state_changed(self, *args):
        self._resize_legal_label()
    def _resize_legal_label(self):
        width, height = self.submit_window.get_size()
        self.label_legal_fineprint.set_size_request(width-24, -1)

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
        review.origin = self.origin
        self.api.submit_review(review)

    def login_successful(self, display_name):
        self.main_notebook.set_current_page(1)
        self._setup_details(self.submit_window, self.app, self.iconname, self.version, display_name)
        return
    
    def _setup_gwibber_gui(self):
        self.gwibber_accounts = self.gwibber_helper.accounts()
        list_length = len(self.gwibber_accounts)
        if list_length == 0:
            self._on_no_gwibber_accounts()
        elif list_length == 1:
            self._on_one_gwibber_account()
        else:
            self._on_multiple_gwibber_accounts()
    
    def _get_gwibber_prefs(self):
        if self.config.has_option("reviews", "gwibber_send"): 
            send = self.config.getboolean("reviews", "gwibber_send")
        else:
            send = False
        
        if self.config.has_option("reviews", "account_id"):
            account_id = self.config.get("reviews", "account_id")
        else:
            account_id = False
        
        return { "gwibber_send" : send, 
                 "account_id" : account_id }
            
    def _on_no_gwibber_accounts(self):
        self.gwibber_hbox.hide()
        self.gwibber_checkbutton.set_active(False)
    
    def _on_one_gwibber_account(self):
        account = self.gwibber_accounts[0]
        self.gwibber_hbox.show()
        self.gwibber_combo.hide()
        acct_text = _("Also post this review to %s (@%s)")  % (
            account['service'].capitalize(), account['username'] )
        self.gwibber_checkbutton.set_label(acct_text)
        # simplifies on_transmit_successful later
        self.gwibber_combo.append_text(acct_text)
        self.gwibber_combo.set_active(0)
        # auto select submit via gwibber checkbutton if saved prefs say True
        self.gwibber_checkbutton.set_active(self.gwibber_prefs['gwibber_send'])
    
    def _on_multiple_gwibber_accounts(self):
        self.gwibber_hbox.show()
        self.gwibber_combo.show()

        # setup accounts combo
        self.gwibber_checkbutton.set_label(_("Also post this review to: "))
        for account in self.gwibber_accounts:
            acct_text =  "%s (@%s)"  % (
                account['service'].capitalize(), account['username'] )
            self.gwibber_combo.append_text(acct_text)

        # add "all" to both combo and accounts (the later is only pseudo)
        self.gwibber_combo.append_text("All my Gwibber services")
        self.gwibber_accounts.append({ "id" : "pseudo-sc-all",
                                     })

        # reapply preferences
        self.gwibber_checkbutton.set_active(self.gwibber_prefs['gwibber_send'])
        gwibber_active_account = 0
        for account in self.gwibber_accounts:
            if account['id'] == self.gwibber_prefs['account_id']:
                gwibber_active_account = self.gwibber_accounts.index(account)
        self.gwibber_combo.set_active(gwibber_active_account)

    def _post_to_one_gwibber_account(self, msg, account):
        """ little helper to facilitate posting message to twitter account
            passed in
        """
        status_text = _("Posting to %s") % account['service'].capitalize()
        self._change_status("progress", status_text)
        return self.gwibber_helper.send_message(msg,account['id'])

    def on_transmit_success(self, api, trans):
        """on successful submission of a review, try to send to gwibber as well"""
        self._run_gwibber_submits(api,trans)
    
    def _get_send_accounts(self, sel_index):
        """return the account referenced by the passed in index, or all accounts
            if the index of the combo points to the pseudo-sc-all string"""
        if self.gwibber_accounts[sel_index]["id"] == "pseudo-sc-all":
            return self.gwibber_accounts
        else:
            return [self.gwibber_accounts[sel_index]]
            
    def _submit_to_gwibber(self,msg,send_accounts):
        """for each send_account passed in, try to submit to gwibber
            then return a list of accounts that failed to submit (empty list if all succeeded"""
        #list of gwibber accounts that failed to submit, used later to allow selective re-send if user desires
        failed_accounts=[]
        for account in send_accounts:
            if account["id"]!= "pseudo-sc-all":
                if not self._post_to_one_gwibber_account(msg, account):
                    failed_accounts.append(account)
        return failed_accounts

    def _run_gwibber_submits(self, api, trans):
        """check if gwibber send should occur and send via gwibber if so"""
        gwibber_success = True
        using_gwibber = self.gwibber_checkbutton.get_active()
        if using_gwibber:
            i = self.gwibber_combo.get_active()
            msg = (self._gwibber_message())
            send_accounts = self._get_send_accounts(i)
            self._save_gwibber_state(True, self.gwibber_accounts[i]['id'])
            #tries to send to gwibber, and gets back any failed accounts
            failed_accounts = self._submit_to_gwibber(msg,send_accounts)
            if len(failed_accounts) > 0:
                gwibber_success = False
                #FIXME: send an error string to this method instead of empty string
                self._on_gwibber_fail(api, trans, failed_accounts, "")
        else:
            # prevent _save_gwibber_state from overwriting the account id
            # in config if the checkbutton was not selected
            self._save_gwibber_state(False, None)
        # run parent handler on gwibber success, otherwise this will be dealt
        # with in _on_gwibber_fail
        if gwibber_success:
            self._success_status()
            BaseApp.on_transmit_success(self, api, trans)
    
    def _gwibber_retry_some(self, api, trans, accounts):
        """ perform selective retrying of gwibber posting, using only
            accounts passed in
        """
        gwibber_success = True
        failed_accounts = []
        msg = (self._gwibber_message())
        
        for account in accounts:
            if not self._post_to_one_gwibber_account(msg, account):
                failed_accounts.append(account)
                gwibber_success = False
        
        if not gwibber_success:
            #FIXME: send an error string to this method instead of empty string
            self._on_gwibber_fail(api, trans, failed_accounts, "")
        else:
            self._success_status()
            BaseApp.on_transmit_success(self, api, trans)
    
    def _success_status(self):
        """Updates status area to show success for 2 seconds then allows window to proceed"""
        self._change_status("success", _("Review submitted."))
        while gtk.events_pending():
            gtk.main_iteration(False)
        time.sleep(2)
    
    def _on_gwibber_fail(self, api, trans, failed_accounts, error):
        self._change_status("fail",_("Problems posting to Gwibber"))
        #list to hold service strings in the format: "Service (@username)"
        failed_services = []
        for account in failed_accounts:
            failed_services.append("%s (@%s)" % (account['service'].capitalize(), account['username']))
        
        failed = len(failed_services)
        
        #sets first part of failed services string to first account in list
        failed_services_string = failed_services[0]
        
        #if more than 1 failed account in list, continues to add service strings to the failed_service_string
        if failed > 1:
            #comma separates services for all accounts in list up to the last one, if there is 3 or more
            if failed > 2:
                for i in range(1,failed-1):
                    failed_services_string = failed_services_string + (", %s" % failed_services[i])
            #final account in list is added to end of string with 'and'
            failed_services_string = failed_services_string + (" and %s" % failed_services[failed-1])
            
        glade_dialog = SimpleGtkbuilderDialog(self.datadir, domain="software-center")
        dialog = glade_dialog.dialog_gwibber_error
        dialog.set_transient_for(self.submit_window)
        dialog.set_markup("There was a problem posting this review to %s." % failed_services_string)
        dialog.format_secondary_text(error)
        result = dialog.run()
        dialog.destroy()
        if result == gtk.RESPONSE_ACCEPT:
            self._gwibber_retry_some(api, trans, failed_accounts)
        else:
            BaseApp.on_transmit_success(self, api, trans)
    
    def _save_gwibber_state(self, gwibber_send, account_id):
        if not self.config.has_section("reviews"):
            self.config.add_section("reviews")
        
        self.config.set("reviews", "gwibber_send", str(gwibber_send))
        if account_id:
            self.config.set("reviews", "account_id", account_id)
        
        self.config.write()
        return
        
    
    def _gwibber_message(self, max_len=140):
        """ build a gwibber message of max_len"""
        def _gwibber_message_string_from_data(appname, rating, summary, link):
            """ helper so that we do not duplicate the "reviewed..." string """
            return _("reviewed %(appname)s in Ubuntu: %(rating)s "
                       "%(summary)s %(link)s") % {
                'appname' : appname,
                'rating'  : rating,
                'summary' : summary,
                'link'    : link }
        
        rating = self.star_rating.get_rating()
        rating_string = ''
        
        #fill star ratings for string
        for i in range(1,6):
            if i <= rating:
                rating_string = rating_string + u"\u2605"
            else:
                rating_string = rating_string + u"\u2606"
                
        review_summary_text = self.review_summary_entry.get_text()
        # FIXME: currently the link is not useful (at all) for most
        #        people not runnig ubuntu
        #app_link = "http://apt.ubuntu.com/p/%s" % self.app.pkgname
        app_link = ""
        gwib_msg = _gwibber_message_string_from_data(
            self.app.name, rating_string, review_summary_text, app_link)
        
        #check char count and ellipsize review summary if larger than 140 chars
        if len(gwib_msg) > max_len:
            chars_to_reduce = len(gwib_msg) - (max_len-1)
            new_char_count = len(review_summary_text) - chars_to_reduce
            review_summary_text = review_summary_text[:new_char_count] + u"\u2026"
            gwib_msg = _gwibber_message_string_from_data(
            self.app.name, rating_string, review_summary_text, app_link)
        
        return gwib_msg

class ReportReviewApp(BaseApp):
    """ report a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"

    APP_ICON_SIZE = 48
    
    SUBMIT_MESSAGE = _(u"Sending report\u2026")

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
        self.submit_window.set_title(_("Flag as Inappropriate"))

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
        for term in [ _(u"Please make a selection\u2026"), 
                      _("Offensive language"), 
                      _("Infringes copyright"), 
                      _("Contains inaccuracies"),
                      _("Other") ]:
            self.combobox_report_summary.append_text(term)
        self.combobox_report_summary.set_active(0)
        
        self.combobox_report_summary.connect(
            "changed", self._enable_or_disable_report_button)

    def _enable_or_disable_report_button(self, widget):
        if self.textview_report.get_buffer().get_char_count() > 0 and self.combobox_report_summary.get_active() != 0:
            self.button_post.set_sensitive(True)
        else:
            self.button_post.set_sensitive(False)

    def _setup_details(self, widget, display_name):

        # title
        m = '<b><span size="x-large">%s</span></b>\n%s %s'
        self.report_title.set_markup(m % (_('Review Infringment'), _('Reported by'), display_name))

        # report label
        self.report_label.set_markup(_('Please give details:'))

        # review summary label
        self.report_summary_label.set_markup(_('Why is this review inappropriate?'))
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

class SubmitUsefulnessApp(BaseApp):
    SUBMIT_MESSAGE = _(u"Sending usefulness\u2026")
    
    def __init__(self, review_id, parent_xid, is_useful, datadir):
        BaseApp.__init__(self, datadir, "submit_usefulness.ui")
        # data
        self.review_id = review_id
        self.is_useful = bool(is_useful)
        # no UI except for error conditions
        self.parent_xid = parent_xid

    # override behavior of baseapp here as we don't actually
    # have a UI by default
    def _get_parent_xid_for_login_window(self):
        return self.parent_xid

    def login_successful(self, display_name):
        logging.debug("submit usefulness")
        self.main_notebook.set_current_page(1)
        self.api.submit_usefulness(self.review_id, self.is_useful)
    
    def on_transmit_failure(self, api, trans, error):
        print "exiting - error: %s" % error
        self.quit(2)

    # override parents run to only trigger login (and subsequent
    # events) but no UI, if this is commented out, there is some
    # stub ui that can be useful for testing
    def run(self):
        self.login()


if __name__ == "__main__":
    try:
        locale.setlocale(locale.LC_ALL, "")
    except:
        logging.exception("setlocale failed, resetting to C")
        locale.setlocale(locale.LC_ALL, "C")

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
        parser.add_option("-O", "--origin")
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
                                      origin=options.origin,
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

    if "submit_usefulness" in sys.argv[0]:
        # check options
        parser.add_option("", "--review-id") 
        parser.add_option("", "--parent-xid")
        parser.add_option("", "--is-useful")
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
        usefulness_app = SubmitUsefulnessApp(datadir=options.datadir,
                                         review_id=options.review_id, 
                                         parent_xid=options.parent_xid,
                                         is_useful=int(options.is_useful))
        usefulness_app.run()

    # main
    gtk.main()
