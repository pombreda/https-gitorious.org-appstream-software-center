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

# the current login state, this is used accross multiple threads
CURRENT_LOGIN_STATE = LOGIN_STATE_UNKNOWN

# the entered username/pw
LOGIN_USERNAME = None
LOGIN_PASSWORD = None


class AuthorizeRequestTokenFromThread(RequestTokenAuthorizationEngine):

    def input_username(self, cached_username, suggested_message):
        """Collect the Launchpad username from the end-user.

        :param cached_username: A username from a previous entry attempt,
        to be presented as the default.
        """
        global CURRENT_LOGIN_STATE 
        print "thread ask username"
        # FIXME: check for valid state transitions
        if CURRENT_LOGIN_STATE != LOGIN_STATE_ASK_USER_AND_PASS:
            CURRENT_LOGIN_STATE = LOGIN_STATE_ASK_USER_AND_PASS
        # wait for username to become available
        while not CURRENT_LOGIN_STATE in (LOGIN_STATE_HAS_USER_AND_PASS,
                                          LOGIN_STATE_USER_CANCEL):
            time.sleep(0.2)
        return LOGIN_USERNAME

    def input_password(self, suggested_message):
        """Collect the Launchpad password from the end-user."""
        print "Input password"
        return LOGIN_PASSWORD

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
        global CURRENT_LOGIN_STATE 
        CURRENT_LOGIN_STATE = LOGIN_STATE_AUTH_FAILURE

    def success(self, suggested_message):
        """The token was successfully authorized."""
        global CURRENT_LOGIN_STATE 
        print "success"
        self.output(suggested_message)
        CURRENT_LOGIN_STATE = LOGIN_STATE_SUCCESS

    # none of the below is needed
    def output(self, message):
        print self.text_wrapper.fill(message)

    def user_refused_to_authorize(self, suggested_message):
        """The user refused to authorize a request token."""
        self.output(suggested_message)
        self.output("\n")

    def user_authorized(self, access_level, suggested_message):
        """The user authorized a request token with some access level."""
        self.output(suggested_message)
        self.output("\n")

    def server_consumer_differs_from_client_consumer(
        self, client_name, real_name, suggested_message):
        """The client seems to be lying or mistaken about its name.

        When requesting a request token, the client told Launchpad
        that its consumer name was "foo". Now the client is telling the
        end-user that its name is "bar". Something is fishy and at the very
        least the end-user should be warned about this.
        """
        self.output("\n")
        self.output(suggested_message)
        self.output("\n")
        
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
        # launchpadlib worker thread
        self._lp = LaunchpadlibWorker()

    def enter_username_password(self):
        global CURRENT_LOGIN_STATE, LOGIN_USERNAME, LOGIN_PASSWORD
        res = self.dialog_review_login.run()
        self.dialog_review_login.hide()
        if res == gtk.RESPONSE_OK:
            LOGIN_USERNAME = self.entry_review_login_email.get_text()
            LOGIN_PASSWORD = self.entry_review_login_password.get_text()
            CURRENT_LOGIN_STATE = LOGIN_STATE_HAS_USER_AND_PASS
        else:
            CURRENT_LOGIN_STATE = LOGIN_STATE_USER_CANCEL
            return ""

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
        self._lp.start()
        # wait for global state change 
        glib.timeout_add(2000, self._wait_state_change)
        # parent
        SimpleGtkbuilderApp.run(self)
    
    def _wait_state_change(self):
        print "gui: _wait_state_change: ", CURRENT_LOGIN_STATE
        if CURRENT_LOGIN_STATE == LOGIN_STATE_ASK_USER_AND_PASS:
            self.enter_username_password()
        elif CURRENT_LOGIN_STATE == LOGIN_STATE_SUCCESS:
            self.enter_review()
        return True

class LaunchpadlibWorker(threading.Thread):

    def run(self):
        print "lp worker thread run"
        self.launchpad = None
        self.lp_login()

    def _wait_state_change(self):
        while True:
            print "worker: _wait_state_change"
            time.sleep(2)

    def lp_login(self):
        global CURRENT_LOGIN_STATE 
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
        CURRENT_LOGIN_STATE = LOGIN_STATE_SUCCESS
        print CURRENT_LOGIN_STATE
        print "/done"
        print self.launchpad

        self._wait_state_change()
        

if __name__ == "__main__":
    # FIXME: provide a package
    review_app = SubmitReviewsApp(datadir="./data", app="2vcard")
    review_app.run()

