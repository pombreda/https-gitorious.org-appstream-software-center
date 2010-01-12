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
import os
import sys
import time
import threading

from gettext import gettext as _
from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib import uris
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

class LaunchpadlibWorker(threading.Thread):

    def __init__(self):
        # init parent
        threading.Thread.__init__(self)
        # the current login state, this is used accross multiple threads
        self.login_state = LOGIN_STATE_UNKNOWN
        # the username/pw to use
        self.login_username = ""
        self.login_password = ""
        self._launchpad = None

    def run(self):
        print "lp worker thread run"
        # login
        self.lp_login()
        # loop
        self._wait_for_commands()

    def _wait_for_commands(self):
        while True:
            print "worker: _wait_state_change"
            time.sleep(0.2)

    def lp_login(self):
        print "lp_login"
        # use cachedir
        cachedir = os.path.expanduser("~/.cache/software-center")
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        print "hello"

        # login into LP with GUI
        self.launchpad = Launchpad.login_with(
            'software-center', 'edge', cachedir,
            allow_access_levels = ['WRITE_PUBLIC'],
            authorizer_class=AuthorizeRequestTokenFromThread)
        # if we are here we are in
        self.login_state = LOGIN_STATE_SUCCESS
        print "/done"
        print self.launchpad

class AuthorizeRequestTokenFromThread(RequestTokenAuthorizationEngine):

    def __new__(cls, *args, **kwargs):
        o = object.__new__(cls)
        # keep the state here (the lp_worker_thead is a singelton)
        o.lp_worker = lp_worker_thread
        return o

    def input_username(self, cached_username, suggested_message):
        print "foo: ", self.lp_worker.login_state
        print "thread ask username"
        # check if user canceled and if so just return ""
        if self.lp_worker.login_state == LOGIN_STATE_USER_CANCEL:
            return ""
        # otherwise go into ASK state
        if self.lp_worker.login_state != LOGIN_STATE_ASK_USER_AND_PASS:
            self.lp_worker.login_state = LOGIN_STATE_ASK_USER_AND_PASS
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

    def enter_review(self):
        res = self.dialog_review_app.run()
        print res
        if res == gtk.RESPONSE_OK:
            print "ok"
            # get a test bug
            test_bug = self._launchpad.bugs[505983]
            print test_bug.title
            text_buffer = self.textview_review.get_buffer()
            text = text_buffer.get_text(text_buffer.get_start_iter(),
                                        text_buffer.get_end_iter())
            print text
            test_bug.description = text
            test_bug.lp_save()

    def run(self):
        # do the launchpad stuff async
        lp_worker_thread.start()
        # wait for  state change 
        glib.timeout_add(200, self._wait_for_login)
        # parent
        SimpleGtkbuilderApp.run(self)
    
    def _wait_for_login(self):
        print "gui: _wait_state_change: ", lp_worker_thread.login_state
        if lp_worker_thread.login_state == LOGIN_STATE_ASK_USER_AND_PASS:
            self.enter_username_password()
        elif lp_worker_thread.login_state == LOGIN_STATE_SUCCESS:
            self.enter_review()
            return False
        return True

# IMPORTANT: create one (module) global LP worker thread here
lp_worker_thread = LaunchpadlibWorker()

if __name__ == "__main__":
    # FIXME: provide a package
    review_app = SubmitReviewsApp(datadir="./data", app="2vcard")
    review_app.run()

