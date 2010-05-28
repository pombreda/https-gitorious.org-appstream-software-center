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

import os
import gobject
gobject.threads_init()
import glib
import logging
import time
import threading

from softwarecenter.distro import get_distro

from launchpadlib.launchpad import Launchpad
from launchpadlib.credentials import RequestTokenAuthorizationEngine
from launchpadlib.uris import EDGE_SERVICE_ROOT, STAGING_SERVICE_ROOT
from paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue


# LP to use
SERVICE_ROOT = EDGE_SERVICE_ROOT

# internal

# the various states that the login can be in
LOGIN_STATE_UNKNOWN = "unkown"
LOGIN_STATE_ASK_USER_AND_PASS = "ask-user-and-pass"
LOGIN_STATE_HAS_USER_AND_PASS = "has-user-pass"
LOGIN_STATE_SUCCESS = "success"
LOGIN_STATE_AUTH_FAILURE = "auth-fail"
LOGIN_STATE_USER_CANCEL = "user-cancel"

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
        self.pending_reports = Queue()
        self._shutdown = False

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        logging.debug("lp worker thread run")
        # login
        self._lp_login()
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            time.sleep(0.2)
            if self._shutdown:
                return

    def _lp_login(self, access_level=['READ_PRIVATE']):
        """ internal LP login code """
        logging.debug("lp_login")
        # use cachedir
        cachedir = SOFTWARE_CENTER_CACHE_DIR
        if not os.path.exists(cachedir):
            os.makedirs(cachedir)
        # login into LP with GUI
        try:
            self._launchpad = Launchpad.login_with(
                'software-center', SERVICE_ROOT, cachedir,
                allow_access_levels = access_level,
                authorizer_class=AuthorizeRequestTokenFromThread)
            self.display_name = self._launchpad.me.display_name
        except Exception, e:
            if type(e) != UserCancelException:
                logging.exception("Launchpad.login_with()")
            self.login_state = LOGIN_STATE_AUTH_FAILURE
            self._shutdown = True
            return
        # check server status
        self.login_state = LOGIN_STATE_SUCCESS
        logging.debug("/done %s" % self._launchpad)

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


class GLaunchpad(gobject.GObject):
    
    __gsignals__ = {
        "login-successful" : (gobject.SIGNAL_RUN_LAST,
                             gobject.TYPE_NONE, 
                             (),
                            ),
        "login-failed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (),
                         ),
        }

    def __init__(self):
        gobject.GObject.__init__(self)
        self.distro = get_distro()

    def login(self, user, password):
        """ log into launchpad, emits login-{successful,failed} signals """
        glib.timeout_add(200, self._wait_for_login)
        self._user = user
        self._password = password
        lp_worker_thread.start()

    def enter_username_password(self):
        lp_worker_thread.login_username = self._user
        lp_worker_thread.login_password = self._password
        lp_worker_thread.login_state = LOGIN_STATE_HAS_USER_AND_PASS        
    
    def get_subscribed_archives(self):
        """ return list of sources.list entries """
        urls = lp_worker_thread._launchpad.me.getArchiveSubscriptionURLs()
        return ["deb %s %s main" % (url, self.distro.get_codename()) for url in urls]

    def get_subscribed_archives_async(self, callback):
        # FIXME: add code
        pass

    def _wait_for_login(self):
        state = lp_worker_thread.login_state

        # hide progress once we got a reply
        # check state
        if state == LOGIN_STATE_AUTH_FAILURE:
            self.emit("login-failed")
            return False
        elif state == LOGIN_STATE_ASK_USER_AND_PASS:
            self.enter_username_password()
        elif state == LOGIN_STATE_SUCCESS:
            self.emit("login-successful")
            return False
        elif state == LOGIN_STATE_USER_CANCEL:
            return False
        return True

# IMPORTANT: create one (module) global LP worker thread here
lp_worker_thread = LaunchpadlibWorker()
# daemon threads make it crash on cancel
#lp_worker_thread.daemon = True


# test code
def _login_success(lp):
    print "success", lp
    print lp.get_subscribed_archives()
def _login_failed(lp):
    print "fail", lp

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys
    user = sys.argv[1]
    print "password: "
    password = sys.stdin.readline().strip()

    lp = GLaunchpad()
    lp.connect("login-successful", _login_success)
    lp.connect("login-failed", _login_failed)
    lp.login(user, password)
    
    # wait
    try:
        glib.MainLoop().run()
    except KeyboardInterrupt:
        lp_worker_thread.shutdown()
