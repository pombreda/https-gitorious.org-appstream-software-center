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

import gettext
import glib
import gtk
import logging
import os
import sys
import time
import threading

from gettext import gettext as _
from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib import uris
from Queue import Queue
from urlparse import urljoin

import softwarecenter.view.dialogs
from softwarecenter.SimpleGtkbuilderApp import SimpleGtkbuilderApp

# the various states that the login can be in
LOGIN_STATE_UNKNOWN = "unkown"
LOGIN_STATE_ASK_USER_AND_PASS = "ask-user-and-pass"
LOGIN_STATE_HAS_USER_AND_PASS = "has-user-pass"
LOGIN_STATE_SUCCESS = "success"
LOGIN_STATE_AUTH_FAILURE = "auth-fail"
LOGIN_STATE_USER_CANCEL = "user-cancel"

class UserCancelException(Exception):
    pass

class LaunchpadlibWorker(threading.Thread):
    """The launchpadlib worker thread - it does not touch the UI
       and only communicates via the following variables:

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
        self.shutdown = False

    def run(self):
        """Main thread run interface, logs into launchpad and waits
           for commands
        """
        print "lp worker thread run"
        # login
        self._lp_login()
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self.shutdown = True

    def queue_review(self, review):
        """ queue a new review for sending to LP """
        print "queue_review", text
        self.pending_reviews.put(review)

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            print "worker: _wait_for_commands", self.login_state
            self._submit_reviews()
            time.sleep(0.2)
            if self.shutdown and self.pending_reviews.empty():
                return

    def _submit_reviews(self):
        """ internal submit code """
        print "_submit_review"
        while not self.pending_reviews.empty():
            review = self.pending_reviews.get()
            print "sending review"
            test_bug = self.launchpad.bugs[505983]
            msg = test_bug.newMessage(subject="test", 
                                      content=review)
            self.pending_reviews.task_done()

    def _lp_login(self):
        """ internal LP login code """
        print "lp_login"
        # use cachedir
        cachedir = os.path.expanduser("~/.cache/software-center")
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        print "hello"

        # login into LP with GUI
        try:
            self.launchpad = Launchpad.login_with(
                'software-center', 'edge', cachedir,
                allow_access_levels = ['WRITE_PUBLIC'],
                authorizer_class=AuthorizeRequestTokenFromThread)
        except Exception, e:
            if type(e) != UserCancelException:
                logging.exception("Launchpad.login_with()")
            self.login_state = LOGIN_STATE_AUTH_FAILURE
            self.shutdown = True
            return
        # if we are here we are in
        self.login_state = LOGIN_STATE_SUCCESS
        print "/done"
        print self.launchpad

class AuthorizeRequestTokenFromThread(RequestTokenAuthorizationEngine):
    """ Internal helper that updates the login_state of
        the modul global lp_worker_thread object
    """

    def __new__(cls, *args, **kwargs):
        o = object.__new__(cls)
        # keep the state here (the lp_worker_thead is a singelton)
        o.lp_worker = lp_worker_thread
        return o

    def input_username(self, cached_username, suggested_message):
        print "input_username: ", self.lp_worker.login_state
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
        print "Input password"
        return self.lp_worker.login_password

    def input_access_level(self, available_levels, suggested_message,
                           only_one_option=None):
        """Collect the desired level of access from the end-user."""
        print "input_access_level"
        return "WRITE_PUBLIC"

    def startup(self, suggested_messages):
        print "startup"

    def authentication_failure(self, suggested_message):
        """The user entered invalid credentials."""
        print "auth failure"
        # ignore auth failures if the user canceled
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            return
        self.lp_worker.login_state = LOGIN_STATE_AUTH_FAILURE

    def success(self, suggested_message):
        """The token was successfully authorized."""
        print "success"
        self.lp_worker.login_state = LOGIN_STATE_SUCCESS

class SubmitReviewsApp(SimpleGtkbuilderApp):
    """ review a given application or package """

    def __init__(self, app, datadir):
        SimpleGtkbuilderApp.__init__(self, 
                                     datadir+"/ui/reviews.ui",
                                     "software-center")
        gettext.bindtextdomain("software-center", "/usr/share/locale")
        gettext.textdomain("software-center")
        # data
        self.app = app

    def enter_username_password(self):
        res = self.dialog_review_login.run()
        self.dialog_review_login.hide()
        if res == gtk.RESPONSE_OK:
            username = self.entry_review_login_email.get_text()
            lp_worker_thread.login_username = username
            password = self.entry_review_login_password.get_text()
            lp_worker_thread.login_password = password
            lp_worker_thread.login_state = LOGIN_STATE_HAS_USER_AND_PASS
        else:
            lp_worker_thread.login_state = LOGIN_STATE_USER_CANCEL
            self.quit()

    def enter_review(self):
        res = self.dialog_review_app.run()
        self.dialog_review_app.hide()
        print res
        if res == gtk.RESPONSE_OK:
            print "ok"
            text_buffer = self.textview_review.get_buffer()
            text = text_buffer.get_text(text_buffer.get_start_iter(),
                                        text_buffer.get_end_iter())
            print text
            lp_worker_thread.queue_review(text)
        # signal thread to finish
        lp_worker_thread.shutdown()
        self.quit()
        
    def show_login_auth_failure(self):
        softwarecenter.view.dialogs.error(None,
                                          _("Authentication failure"),
                                          _("Sorry, please try again"))

    def quit(self):
        lp_worker_thread.join()
        gtk.main_quit()

    def run(self):
        # do the launchpad stuff async
        lp_worker_thread.start()
        # wait for  state change 
        glib.timeout_add(200, self._wait_for_login)
        # parent
        SimpleGtkbuilderApp.run(self)
    
    def _wait_for_login(self):
        print "gui: _wait_state_change: ", lp_worker_thread.login_state
        state = lp_worker_thread.login_state
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
        return True

# IMPORTANT: create one (module) global LP worker thread here
lp_worker_thread = LaunchpadlibWorker()

if __name__ == "__main__":
    # FIXME: provide a package
    review_app = SubmitReviewsApp(datadir="./data", app="2vcard")
    review_app.run()

