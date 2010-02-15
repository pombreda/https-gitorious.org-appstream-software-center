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

import softwarecenter.view.dialogs

from softwarecenter.db.database import Application
from softwarecenter.db.reviews import Review
from softwarecenter.utils import *
from softwarecenter.SimpleGtkbuilderApp import SimpleGtkbuilderApp

# the various states that the login can be in
LOGIN_STATE_UNKNOWN = "unkown"
LOGIN_STATE_ASK_USER_AND_PASS = "ask-user-and-pass"
LOGIN_STATE_HAS_USER_AND_PASS = "has-user-pass"
LOGIN_STATE_SUCCESS = "success"
LOGIN_STATE_AUTH_FAILURE = "auth-fail"
LOGIN_STATE_USER_CANCEL = "user-cancel"

# the SUBMIT url
SUBMIT_POST_URL = "http://localhost:8080/reviews/en/ubuntu/lucid/submit_review"


# LP to use
SERVICE_ROOT = EDGE_SERVICE_ROOT

class UserCancelException(Exception):
    """ user pressed cancel """
    pass

class LaunchpadlibWorker(threading.Thread):
    """The launchpadlib worker thread - it does not touch the UI
       and only communicates via the following:

       "login_state" - the current LOGIN_STATE_* value
       
       To input reviews call "queue_review()"
       When no longer needed, call "shutdown()"
    """
    
    def __init__(self):
        # init parent
        threading.Thread.__init__(self)
        # the current login state, this is used accross multiple threads
        self.login_state = LOGIN_STATE_UNKNOWN
        # the username/pw to use
        self.login_username = ""
        self.login_password = ""
        self._launchpad = None
        self.pending_reviews = Queue()
        self._shutdown = False

    def run(self):
        """Main thread run interface, logs into launchpad and waits
           for commands
        """
        logging.debug("lp worker thread run")
        # login
        self._lp_login()
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def queue_review(self, review):
        """ queue a new review for sending to LP """
        logging.debug("queue_review %s" % review)
        self.pending_reviews.put(review)

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            #logging.debug("worker: _wait_for_commands %s" % self.login_state)
            self._submit_reviews()
            time.sleep(0.2)
            if self._shutdown and self.pending_reviews.empty():
                return

    def _submit_reviews(self):
        """ the actual submit function """
        self._submit_reviews_POST()
        #self._submit_reviews_LP()
            
    def _submit_reviews_POST(self):
        """ http POST based submit """
        while not self.pending_reviews.empty():
            logging.debug("_submit_review")
            review = self.pending_reviews.get()
            review.person = self.launchpad.me.name
            data = { 'package_name' : review.app.pkgname,
                     'app_name' : review.app.appname,
                     'summary' : review.summary,
                     'text' : review.text,
                     'date' : review.date,
                     'rating': review.rating,
                     'name' : review.person,
                     # send the token, ideally we would not send
                     # it but instead send a pre-made request
                     # that uses  "3.4.2.  HMAC-SHA1" - but it
                     # seems that LP does not support that at this
                     # point 
                     'token' : self.launchpad.credentials.access_token.key,
                     'token-secret' : self.launchpad.credentials.access_token.secret,
                     }
            f = urllib.urlopen(SUBMIT_POST_URL, urllib.urlencode(data))
            res = f.read()
            print res
            f.close()
            self.pending_reviews.task_done()
        

    def _submit_reviews_LP(self):
        """ launchpadlib based submit """
        while not self.pending_reviews.empty():
            logging.debug("_submit_review")
            review = self.pending_reviews.get()
            review.person = self.launchpad.me.name
            logging.debug("sending review %s" % review.to_xml())
            # FIXME: this needs to be replaced with the actual API
            test_bug = self.launchpad.bugs[505983]
            msg = test_bug.newMessage(subject=review.summary, 
                                      content=review.to_xml())
            self.pending_reviews.task_done()

    def _lp_login(self):
        """ internal LP login code """
        logging.debug("lp_login")
        # use cachedir
        cachedir = os.path.expanduser("~/.cache/software-center")
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        # login into LP with GUI
        try:
            self.launchpad = Launchpad.login_with(
                'software-center', SERVICE_ROOT, cachedir,
                allow_access_levels = ['READ_PUBLIC'],
                authorizer_class=AuthorizeRequestTokenFromThread)
        except Exception, e:
            if type(e) != UserCancelException:
                logging.exception("Launchpad.login_with()")
            self.login_state = LOGIN_STATE_AUTH_FAILURE
            self._shutdown = True
            return
        # if we are here we are in
        self.login_state = LOGIN_STATE_SUCCESS
        logging.debug("/done %s" % self.launchpad)

class AuthorizeRequestTokenFromThread(RequestTokenAuthorizationEngine):
    """ Internal helper that updates the login_state of
        the modul global lp_worker_thread object
    """

    # we need this to give the engine a place to store the state
    # for the UI
    def __new__(cls, *args, **kwargs):
        o = object.__new__(cls)
        # keep the state here (the lp_worker_thead global to this module)
        o.lp_worker = lp_worker_thread
        return o

    def input_username(self, cached_username, suggested_message):
        logging.debug( "input_username: %s" %self.lp_worker.login_state)
        # otherwise go into ASK state
        if not self.lp_worker.login_state in (LOGIN_STATE_ASK_USER_AND_PASS,
                                              LOGIN_STATE_AUTH_FAILURE,
                                              LOGIN_STATE_USER_CANCEL):
            self.lp_worker.login_state = LOGIN_STATE_ASK_USER_AND_PASS
        # check if user canceled and if so just return ""
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            raise UserCancelException
        # wait for username to become available
        while not self.lp_worker.login_state in (LOGIN_STATE_HAS_USER_AND_PASS,
                                                 LOGIN_STATE_USER_CANCEL):
            time.sleep(0.2)
        # note: returning None here make lplib open a registration page
        #       in the browser
        return self.lp_worker.login_username

    def input_password(self, suggested_message):
        logging.debug( "Input password size %s" % len(self.lp_worker.login_password))
        return self.lp_worker.login_password

    def input_access_level(self, available_levels, suggested_message,
                           only_one_option=None):
        """Collect the desired level of access from the end-user."""
        logging.debug("input_access_level")
        return "WRITE_PUBLIC"

    def startup(self, suggested_messages):
        logging.debug("startup")

    def authentication_failure(self, suggested_message):
        """The user entered invalid credentials."""
        logging.debug("auth failure")
        # ignore auth failures if the user canceled
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            return
        self.lp_worker.login_state = LOGIN_STATE_AUTH_FAILURE

    def success(self, suggested_message):
        """The token was successfully authorized."""
        logging.debug("success")
        self.lp_worker.login_state = LOGIN_STATE_SUCCESS

class SubmitReviewsApp(SimpleGtkbuilderApp):
    """ review a given application or package """

    LOGIN_IMAGE = "/usr/share/software-center/images/ubuntu-cof.png"
    STAR_IMAGE = "/usr/share/software-center/images/star-yellow.png"
    DARK_STAR_IMAGE = "/usr/share/software-center/images/star-dark.png"

    APP_ICON_SIZE = 48

    def __init__(self, app, version, iconname, parent_xid, datadir):
        SimpleGtkbuilderApp.__init__(self, 
                                     datadir+"/ui/reviews.ui",
                                     "software-center")
        gettext.bindtextdomain("software-center", "/usr/share/locale")
        gettext.textdomain("software-center")
        
        # additional icons come from app-install-data
        self.icons = gtk.icon_theme_get_default()
        self.icons.append_search_path("/usr/share/app-install/icons/")

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

    def enter_username_password(self):
        self.progressbar_connecting.hide()
        res = self.dialog_review_login.run()
        self.dialog_review_login.hide()
        if res == gtk.RESPONSE_OK:
            username = self.entry_review_login_email.get_text()
            lp_worker_thread.login_username = username
            password = self.entry_review_login_password.get_text()
            lp_worker_thread.login_password = password
            lp_worker_thread.login_state = LOGIN_STATE_HAS_USER_AND_PASS
            self.progressbar_connecting.show()
        else:
            lp_worker_thread.login_state = LOGIN_STATE_USER_CANCEL
            self.quit()

    def on_entry_summary_changed(self, widget):
        self._enable_or_disable_post_button()

    def _enable_or_disable_post_button(self):
        if self.entry_summary.get_text() and self.rating > 0:
            self.button_post_review.set_sensitive(True)
        else:
            self.button_post_review.set_sensitive(False)
            
    def enter_review(self):
        self.progressbar_connecting.hide()
        self.dialog_review_app.set_sensitive(True)
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
            lp_worker_thread.queue_review(review)
        # signal thread to finish
        lp_worker_thread.shutdown()
        self.quit()
        
    def show_login_auth_failure(self):
        softwarecenter.view.dialogs.error(self.dialog_review_app,
                                          _("Authentication failure"),
                                          _("Sorry, please try again"))

    def quit(self):
        lp_worker_thread.join()
        gtk.main_quit()

    def run(self):
        # show main dialog insensitive until we are logged in
        self.dialog_review_app.set_sensitive(False)
        self.progressbar_connecting.set_text(_("Connecting..."))
        self.dialog_review_app.show()
        
        # do the launchpad stuff async
        lp_worker_thread.start()
        # wait for  state change 
        glib.timeout_add(200, self._wait_for_login)
        # parent
        SimpleGtkbuilderApp.run(self)
    
    def _wait_for_login(self):
        state = lp_worker_thread.login_state
        # hide progress once we got a reply
        # check state
        if state == LOGIN_STATE_AUTH_FAILURE:
            self.show_login_auth_failure()
            self.enter_username_password()
        elif state == LOGIN_STATE_ASK_USER_AND_PASS:
            self.enter_username_password()
        elif state == LOGIN_STATE_SUCCESS:
            self.enter_review()
            return False
        elif state == LOGIN_STATE_USER_CANCEL:
            return False
        # pulse
        self.progressbar_connecting.pulse()
        return True

# IMPORTANT: create one (module) global LP worker thread here
lp_worker_thread = LaunchpadlibWorker()

if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    
    # check options
    parser = OptionParser()
    parser.add_option("-a", "--appname")
    parser.add_option("-p", "--pkgname")
    parser.add_option("-i", "--iconname")
    parser.add_option("-V", "--version")
    parser.add_option("", "--parent-xid")
    parser.add_option("", "--debug",
                      action="store_true", default=False)
    parser.add_option("", "--datadir", 
                      default="/usr/share/software-center/")
    (options, args) = parser.parse_args()

    if not (options.pkgname and options.version):
        parser.error(_("Missing arguments"))
    
    if options.debug:
       logging.basicConfig(level=logging.DEBUG)                        

    # initialize and run
    app = Application(options.appname, options.pkgname)
    review_app = SubmitReviewsApp(datadir=options.datadir,
                                  app=app, 
                                  parent_xid=options.parent_xid,
                                  iconname=options.iconname,
                                  version=options.version)
    review_app.run()

