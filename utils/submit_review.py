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
import multiprocessing
import os
import sys
import tempfile
import time
import threading
import urllib

from gettext import gettext as _
from Queue import Queue
from optparse import OptionParser

from softwarecenter.backend.restfulclient import RestfulClientWorker, UBUNTU_SSO_SERVICE
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthToken

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
        self.rnrclient = RatingsAndReviewsAPI(auth=auth)

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
                self.rnrclient.report_abuse(review_id=review_id,
                                            reason=summary,
                                            text=text)
                self._transmit_state = TRANSMIT_STATE_DONE
            except Exception as e:
                logging.exception("report_abuse failed")
                self._write_exception_html_log_if_needed(e)
                self._transmit_state = TRANSMIT_STATE_ERROR
                self._transmit_error_str = _("Failed to submit report")
            self.pending_reports.task_done()

    def _write_exception_html_log_if_needed(self, e):
        # write out a "oops.html" 
        if type(e) is piston_mini_client.APIError:
            f=tempfile.NamedTemporaryFile(
                prefix="sc_submit_oops_", suffix=".html", delete=False)
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
                self.rnrclient.submit_review(review=piston_review)
                self._transmit_state = TRANSMIT_STATE_DONE
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
        self.token = None
        self.display_name = None
        self._login_successful = False
        # status spinner
        self.status_spinner = gtk.Spinner()
        self.login_hbox.pack_start(self.status_spinner, False)
        self.login_hbox.reorder_child(self.status_spinner, 0)
        self.status_spinner.show()
        glib.timeout_add(500, self._glib_whoami_done)

    def run(self):
        # initially display a 'Connecting...' page
        self.main_notebook.set_current_page(0)
        self.login_status_label.set_markup('<big>%s</big>' % _("Signing in..."))
        self.status_spinner.start()
        self.dialog_main.show()
        # now run the loop
        self.login()

    def quit(self):
        sys.exit(0)

    def login_successful(self, display_name):
        """ callback when the login was successful """
        pass

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

    def _maybe_login_successful(self, sso, oauth_result):
        """ called after we have the token, then we go and figure out our name """
        self.token = oauth_result
        # now get the user name
        token = OAuthToken(self.token["token"], self.token["token_secret"])
        authorizer = OAuthAuthorizer(self.token["consumer_key"],
                                     self.token["consumer_secret"],
                                     access_token=token)
        self.restful_worker_thread = RestfulClientWorker(authorizer, UBUNTU_SSO_SERVICE)
        self.restful_worker_thread.start()
        # now get "me"
        self.restful_worker_thread.queue_request("accounts.me", (), {},
                                                 self._thread_whoami_done,
                                                 self._thread_whoami_error)

    def _thread_whoami_done(self, result):
        self.display_name = result["displayname"]
        self._login_successful = True

    def _create_gratings_api(self):
        self.api = GRatingsAndReviews(self.token)
        self.api.connect("transmit-start", self.on_transmit_start)
        self.api.connect("transmit-success", self.on_transmit_success)
        self.api.connect("transmit-failure", self.on_transmit_failure)

    def on_transmit_start(self, api, trans):
        self.action_area.set_sensitive(False)
        # FIXME: add little spinner here
        self.label_transmit_status.set_text(_("submitting review..."))

    def on_transmit_success(self, api, trans):
        self.api.shutdown()
        self.quit()

    def on_transmit_failure(self, api, trans, error):
        # FIXME: show little error symbol here
        self.label_transmit_status.set_text(error)
        self.action_area.set_sensitive(True)

    def _glib_whoami_done(self):
        if self._login_successful:
            self._create_gratings_api()
            self.login_successful(self.display_name)
            return False
        return True

    def _thread_whoami_error(self, e):
        print "error: ", e

    def login(self):
        appname = _("Ubuntu Software Center")
        login_text = _("To review software or to report abuse you need to "
                       "sign in to a Ubuntu Single Sign-On account.")
        self.sso = LoginBackendDbusSSO(self.dialog_main.window.xid, appname,
                                       login_text)
        self.sso.connect("login-successful", self._maybe_login_successful)
        self.sso.login_or_register()

    def on_button_cancel_clicked(self, button=None):
        # bring it down gracefully
        self.api.shutdown()
        while gtk.events_pending():
            gtk.main_iteration()
        sys.exit(0)

class SubmitReviewsApp(BaseApp):
    """ review a given application or package """


    STAR_SIZE = (32, 32)
    APP_ICON_SIZE = 48

    def __init__(self, app, version, iconname, parent_xid, datadir):
        BaseApp.__init__(self, datadir, "submit_review.ui")

        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path("/usr/share/app-install/icons/")
        self.dialog_main.connect("destroy", self.on_button_cancel_clicked)
        self._add_spellcheck_to_textview(self.textview_review)

        # interactive star rating
        self.star_rating = StarRatingSelector(0, star_size=self.STAR_SIZE)
        self.star_caption = StarCaption()

        self.star_rating.set_caption_widget(self.star_caption)
        self.star_rating.set_padding(3, 3, 3, 0)
        self.star_caption.show()

        self.review_summary_vbox.pack_start(self.star_rating, False)
        self.review_summary_vbox.reorder_child(self.star_rating, 0)
        self.review_summary_vbox.pack_start(self.star_caption, False, False)
        self.review_summary_vbox.reorder_child(self.star_caption, 1)

        # data
        self.app = app
        self.version = version
        self.iconname = iconname
        
        # title
        self.dialog_main.set_title(_("Review %s" % self.app.name))

        self.review_summary_entry.connect('changed', self._on_mandatory_fields_changed)
        self.star_rating.connect('changed', self._on_mandatory_fields_changed)

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.dialog_main.realize()
                self.dialog_main.window.set_transient_for(win)

        self.dialog_main.set_position(gtk.WIN_POS_MOUSE)

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
        return

    def _on_mandatory_fields_changed(self, widget):
        self._enable_or_disable_post_button()

    def _enable_or_disable_post_button(self):
        if self.review_summary_entry.get_text() and self.star_rating.get_rating():
            self.review_post.set_sensitive(True)
        else:
            self.review_post.set_sensitive(False)

    def on_review_cancel_clicked(self, button):
        while gtk.events_pending():
            gtk.main_iteration()
        self.api.shutdown()
        self.quit()

    def on_review_post_clicked(self, button):
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
        self._setup_details(self.dialog_main, self.app, self.iconname, self.version, display_name)
        return


class ReportReviewApp(BaseApp):
    """ report a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"

    APP_ICON_SIZE = 48

    def __init__(self, review_id, parent_xid, datadir):
        BaseApp.__init__(self, datadir, "report_abuse.ui")
        self.dialog_main.connect("destroy", self.on_button_cancel_clicked)

        # status
        self._add_spellcheck_to_textview(self.textview_report)

        ## make button sensitive when textview has content
        self.textview_report.get_buffer().connect(
            "changed", self._enable_or_disable_report_button)

        # data
        self.review_id = review_id

        # title
        self.dialog_main.set_title(_("Report an infringment"))

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.dialog_main.realize()
                self.dialog_main.window.set_transient_for(win)
        # mousepos
        self.dialog_main.set_position(gtk.WIN_POS_MOUSE)
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
            self.report_post.set_sensitive(True)
        else:
            self.report_post.set_sensitive(False)

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

    def on_report_post_clicked(self, button):
        logging.debug("report_abuse ok button")
        report_summary = self.combobox_report_summary.get_active_text()
        text_buffer = self.textview_report.get_buffer()
        report_text = text_buffer.get_text(text_buffer.get_start_iter(),
                                           text_buffer.get_end_iter())
        self.api.report_abuse(self.review_id, report_summary, report_text)

    def on_report_cancel_clicked(self, button):
        while gtk.events_pending():
            gtk.main_iteration()
        self.api.shutdown()
        self.quit()
        
    def login_successful(self, display_name):
        self.main_notebook.set_current_page(1)
        #self.label_reporter.set_text(display_name)
        self._setup_details(self.dialog_main, display_name)
    
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
        print "submit_review mode"
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

        # initialize and run
        report_app = ReportReviewApp(datadir=options.datadir,
                                      review_id=options.review_id, 
                                      parent_xid=options.parent_xid)
        report_app.run()

    # main
    gtk.main()
