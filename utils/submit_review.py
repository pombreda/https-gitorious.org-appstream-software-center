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
import gettext
import glib
import gtk
import locale
import logging
import os
import subprocess
import sys
import time
import threading
import urllib
import urllib2

from gettext import gettext as _
from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib.uris import EDGE_SERVICE_ROOT, STAGING_SERVICE_ROOT
from Queue import Queue
from optparse import OptionParser
from urlparse import urljoin

from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthConsumer, OAuthToken

import softwarecenter.view.dialogs

from softwarecenter.paths import *
from softwarecenter.backend.login_sso import LoginBackendDbusSSO
from softwarecenter.backend.restfulclient import RestfulClientWorker, UBUNTU_SSO_SERVICE
from softwarecenter.db.database import Application
from softwarecenter.db.reviews import Review
from softwarecenter.utils import *
from softwarecenter.SimpleGtkbuilderApp import SimpleGtkbuilderApp
from softwarecenter.distro import get_distro

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

class Worker(threading.Thread):
    
    def __init__(self):
        # init parent
        threading.Thread.__init__(self)
        self.pending_reviews = Queue()
        self.pending_reports = Queue()
        self._shutdown = False
        self.display_name = "No display namee"

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

    def queue_review(self, review):
        """ queue a new review for sending to LP """
        logging.debug("queue_review %s" % review)
        self.pending_reviews.put(review, token)

    def queue_report(self, report):
        """ queue a new report for sending to LP """
        logging.debug("queue_report")
        self.pending_reports.put(report, token)

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            #logging.debug("worker: _wait_for_commands %s" % self.login_state)
            self._submit_reviews()
            self._submit_reports()
            time.sleep(0.2)
            if (self._shutdown and
                self.pending_reviews.empty() and
                self.pending_reports.empty()):
                return

    def _submit_reports(self):
        """ the actual report function """
        self._submit_report_POST()

    def _submit_report_POST(self):
        while not self.pending_reports.empty():
            logging.debug("POST report")
            (review_id, summary, text, token) = self.pending_reports.get()
            data = { 'reason' : summary,
                     'text' : text,
                     'token' : self.token.key,
                     'token-secret' : token.secret,
                     }
            url = REPORT_POST_URL % review_id
            f = urllib.urlopen(url, urllib.urlencode(data))
            res = f.read()
            print res
            f.close()
            self.pending_reports.task_done()

    def _submit_reviews(self):
        """ the actual submit function """
        self._submit_reviews_POST()
            
    def _submit_reviews_POST(self):
        """ http POST based submit """
        while not self.pending_reviews.empty():
            logging.debug("_submit_review")
            review, token = self.pending_reviews.get()
            data = { 'package_name' : review.app.pkgname,
                     'app_name' : review.app.appname,
                     'summary' : review.summary,
                     'package_version' : review.package_version,
                     'text' : review.text,
                     'date' : review.date,
                     'rating': review.rating,
                     'name' : review.person,
                     # send the token, ideally we would not send
                     # it but instead send a pre-made request
                     # that uses  "3.4.2.  HMAC-SHA1" - but it
                     # seems that LP does not support that at this
                     # point 
                     'token' : token.key,
                     'token-secret' : token.secret,
                     }
            f = urllib.urlopen(SUBMIT_POST_URL, urllib.urlencode(data))
            res = f.read()
            print res
            f.close()
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

    def __init__(self, datadir):
        SimpleGtkbuilderApp.__init__(self, datadir+"/ui/reviews.ui", "software-center")
        self.token = None

    def login_successful(self, sso, oauth_result):
        """ callback when the login was successful """
        pass

    def _maybe_login_successful(self, sso, oauth_result):
        """ called after we have the token, then we go and figure out our name """
        self.token = oauth_result
        # now get the user name
        token = OAuthToken(self.token["token"], self.token["token_secret"])
        consumer = OAuthConsumer(self.token["consumer_key"], "")
        authorizer = OAuthAuthorizer(consumer.key, access_token=token)
        self.restful_worker_thread = RestfulClientWorker(authorizer, UBUNTU_SSO_SERVICE)
        self.restful_worker_thread.start()
        # now get "me"
        self.restful_worker_thread.queue_request("accounts.me", (), {},
                                                 self._thread_whoami_done,
                                                 self._thread_whoami_error)


    def _thread_whoami_done(self, result):
        print "result: ", result

    def _thread_whoami_error(self, e):
        print "error: ", e


    def login(self):
        self.sso = LoginBackendDbusSSO(self.dialog_main.window.xid)
        self.sso.connect("login-successful", self._maybe_login_successful)
        self.sso.login()

    def run_loop(self):
        # do the io stuff async
        #worker_thread.start()
        # login and run
        self.login()
        res = SimpleGtkbuilderApp.run(self)

    def on_button_cancel_clicked(self, button=None):
        # bring it down gracefully
        worker_thread.shutdown()
        self.dialog_main.hide()
        while gtk.events_pending():
            gtk.main_iteration()
        gtk.main_quit()

class SubmitReviewsApp(BaseApp):
    """ review a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"
    STAR_IMAGE = "/usr/share/software-center/images/star-yellow.png"
    DARK_STAR_IMAGE = "/usr/share/software-center/images/star-dark.png"

    APP_ICON_SIZE = 48

    def __init__(self, app, version, iconname, parent_xid, datadir):
        BaseApp.__init__(self, datadir)
        
        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path("/usr/share/app-install/icons/")
        self.dialog_main = self.dialog_review_app

        # spinner & error
        self.label_error = self.label_review_error
        self.hbox_error = self.hbox_review_error
        self.spinner_status = gtk.Spinner()
        self.spinner_status.show()
        self.alignment_status.add(self.spinner_status)

        # data
        self.app = app
        self.version = version
        self.iconname = iconname
        self.rating = 0
        # title
        self.dialog_review_app.set_title(_("Review %s" % self.app.name))
        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.dialog_review_app.realize()
                self.dialog_review_app.window.set_transient_for(win)
        self.dialog_review_app.set_position(gtk.WIN_POS_MOUSE)
        # set pw dialog transient for main window
        self.dialog_review_login.set_transient_for(self.dialog_review_app)
        self.dialog_review_login.set_modal(True)
        self._init_icons()
        # events
        for i in range(1,6):
            eventbox = getattr(self, "eventbox_review_%i" % i)
            eventbox.connect("button-press-event",
                             self.on_image_review_star_button_press_event,
                             i)
        self.label_name.set_markup("<big>%s</big>\n<small>%s</small>" % (
                self.app.name, self.version))
    
    def _init_icons(self):
        """ init the icons """
        self.image_review_login.set_from_file(self.LOGIN_IMAGE)
        self._update_rating()
        if self.iconname:
            icon = self.icons.load_icon(self.iconname, self.APP_ICON_SIZE, 0)
            if icon:
                self.image_review_app.set_from_pixbuf(icon)

    def _update_rating(self):
        logging.debug("_update_rating %s" % self.rating)
        for i in range(1, self.rating+1):
            img = getattr(self, "image_review_star%i" % i)
            img.set_from_file(self.STAR_IMAGE)
        for i in range(self.rating+1, 6):
            img = getattr(self, "image_review_star%i" % i)
            img.set_from_file(self.DARK_STAR_IMAGE)
        self._enable_or_disable_post_button()

    def on_image_review_star_button_press_event(self, widget, event, data):
        self.rating = data
        self._update_rating()

    def on_entry_summary_changed(self, widget):
        self._enable_or_disable_post_button()

    def _enable_or_disable_post_button(self):
        if self.entry_summary.get_text() and self.rating > 0:
            self.button_post_review.set_sensitive(True)
        else:
            self.button_post_review.set_sensitive(False)
            
    def enter_review(self):
        self.hbox_status.hide()
        self.table_review_main.set_sensitive(True)
        res = self.dialog_review_app.run()
        self.dialog_review_app.hide()
        if res == gtk.RESPONSE_OK:
            logging.debug("enter_review ok button")
            review = Review(self.app)
            text_buffer = self.textview_review.get_buffer()
            review.text = text_buffer.get_text(text_buffer.get_start_iter(),
                                               text_buffer.get_end_iter())
            review.summary = self.entry_summary.get_text()
            review.date = datetime.datetime.now()
            review.language = get_language()
            review.rating = self.rating
            review.package_version = self.version
            worker_thread.queue_review(review)
        # signal thread to finish
        worker_thread.shutdown()
        self.quit()

    def run(self):
        # show main dialog insensitive until we are logged in
        self.table_review_main.set_sensitive(False)
        self.label_status.set_text(_("Connecting..."))
        self.spinner_status.start()
        self.dialog_review_app.show()
        # now run the loop
        res = self.run_loop()

    def login_successful(self, sso, oauth_result):
        BaseApp.login_successful(self, sso, oauth_result)
        self.label_reviewer.set_text(worker_thread.display_name)
        self.enter_review()

class ReportReviewApp(BaseApp):
    """ report a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"

    APP_ICON_SIZE = 48

    def __init__(self, review_id, parent_xid, datadir):
        BaseApp.__init__(self, datadir)
        self.dialog_main = self.dialog_report_app
        
        # spinner & error label
        self.label_error = self.label_report_error
        self.hbox_error = self.hbox_report_error
        self.hbox_status = self.hbox_report_status
        self.spinner_status = gtk.Spinner()
        self.spinner_status.show()
        self.alignment_report_status.add(self.spinner_status)

        # make button sensitive when textview has content
        self.textview_report_text.get_buffer().connect(
            "changed", self._enable_or_disable_report_button)

        # data
        self.review_id = review_id

        # parent xid
        if parent_xid:
            win = gtk.gdk.window_foreign_new(int(parent_xid))
            if win:
                self.dialog_report_app.realize()
                self.dialog_report_app.window.set_transient_for(win)
        self.dialog_report_app.set_position(gtk.WIN_POS_MOUSE)
        # set pw dialog transient for main window
        self.dialog_review_login.set_transient_for(self.dialog_report_app)
        self.dialog_review_login.set_modal(True)
        # simple APIs ftw!
        self.combobox_report_summary = gtk.combo_box_new_text()
        self.combobox_report_summary.show()
        self.alignment_report_summary.add(self.combobox_report_summary)
        for r in [ _("Unspecified"), 
                   _("Offensive language"), 
                   _("Infringes copyright"), 
                   _("Not about this software"), 
                   _("Other") ]: 
            self.combobox_report_summary.append_text(r)
        self.combobox_report_summary.set_active(0)

    def _enable_or_disable_report_button(self, buf):
        if buf.get_char_count() > 0:
            self.button_post_report.set_sensitive(True)
        else:
            self.button_post_report.set_sensitive(False)

    def report_abuse(self):
        self.hbox_report_status.hide()
        self.vbox_report_main.set_sensitive(True)
        res = self.dialog_report_app.run()
        self.dialog_report_app.hide()
        if res == gtk.RESPONSE_OK:
            logging.debug("report_abuse ok button")
            report_summary = self.combobox_report_summary.get_active_text()
            text_buffer = self.textview_report_text.get_buffer()
            report_text = text_buffer.get_text(text_buffer.get_start_iter(),
                                               text_buffer.get_end_iter())
            worker_thread.queue_report((self.review_id,
                                           report_summary, 
                                           report_text))
        # signal thread to finish
        worker_thread.shutdown()
        self.quit()
        
    def run(self):
        # show main dialog insensitive until we are logged in
        self.vbox_report_main.set_sensitive(False)
        self.label_report_status.set_text(_("Connecting..."))
        self.spinner_status.start()
        self.dialog_report_app.show()
        # start the async loop
        self.run_loop()

    def login_successful(self, sso, oauth_result):
        BaseApp.login_successful(self, sso, oauth_result)
        self.label_reporter.set_text(worker_thread.display_name)
        self.report_abuse()

    
# IMPORTANT: create one (module) global LP worker thread here
worker_thread = Worker()
# daemon threads make it crash on cancel
#lp_worker_thread.daemon = True

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
