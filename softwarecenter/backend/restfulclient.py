#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2010 Canonical
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

# possible workaround for bug #599332 is to try to import lazr.restful
# import lazr.restful
# import lazr.restfulclient

from lazr.restfulclient.resource import ServiceRoot
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthConsumer, OAuthToken

from paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue

UBUNTU_SSO_SERVICE = "https://login.staging.ubuntu.com/api/1.0"
UBUNTU_SOFTWARE_CENTER_AGENT_SERVICE = "http://localhost:8000/api/1.0"

class RestfulClientWorker(threading.Thread):
    """ a generic worker thread for a lazr.restfulclient """

    def __init__(self, authorizer, service_root):
        """ init the thread """
        threading.Thread.__init__(self)
        self._service_root_url = service_root
        self._authorizer = authorizer
        self._pending_requests = Queue()
        self._shutdown = False

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        logging.debug("lp worker thread run")
        self.service = ServiceRoot(self._authorizer, self._service_root_url)
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def queue_request(self, func, args, kwargs, result_callback, error_callback):
        """
        queue a (remote) command for execution, the result_callback will
        call with the result_list when done (that function will be
        called async)
        """
        self._pending_requests.put((func, args, kwargs, result_callback, error_callback))

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            while not self._pending_requests.empty():
                logging.debug("found pending request")
                (func_str, args, kwargs, result_callback, error_callback) = self._pending_requests.get()
                # run func async
                try:
                    func = self.service
                    for part in func_str.split("."):
                        func = getattr(func, part)
                    res = func(*args, **kwargs)
                except Exception ,e:
                    error_callback(e)
                else:
                    result_callback(res)
                self._pending_requests.task_done()
            # wait a bit
            time.sleep(0.1)
            if (self._shutdown and
                self._pending_requests.empty()):
                return

class SoftwareCenterAgent(gobject.GObject):

    __gsignals__ = {
        "available-for-me" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT,),
                             ),
        "available" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT,),
                             ),
        }

    AVAILABLE_FOR_ME = "subscriptions.getForOAuthToken"
    AVAILABLE = "applications.filter"

    def __init__(self):
        gobject.GObject.__init__(self)
        self.service = UBUNTU_SOFTWARE_CENTER_AGENT_SERVICE
        # setup restful client
        empty_token = OAuthToken("", "")
        authorizer = OAuthAuthorizer("software-center", access_token=empty_token)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()

    def _available_for_me_done(self, result):
        print "result: ", result
        self.emit("available-for-me", result)

    def _available_for_me_error(self, error):
        print "_available_for_me_error:", error
        
    def available_for_me(self, oauth_token):
        kwargs = { "token_name" : "software-center", 
                   "oauth_token" : oauth_token,
                 }
        self.worker_thread.queue_request(self.AVAILABLE_FOR_ME, (), kwargs,
                                         self._available_for_me_done,
                                         self._available_for_me_error)


class UbuntuSSOlogin(gobject.GObject):

    __gsignals__ = {
        "login-successful" : (gobject.SIGNAL_RUN_LAST,
                             gobject.TYPE_NONE, 
                             (gobject.TYPE_PYOBJECT,),
                            ),
        "login-failed" : (gobject.SIGNAL_RUN_LAST,
                          gobject.TYPE_NONE, 
                          (),
                         ),
        "need-username-password" : (gobject.SIGNAL_RUN_LAST,
                                    gobject.TYPE_NONE, 
                                    (),
                                   ),
        }

    SSO_AUTHENTICATE_FUNC = "authentications.authenticate"

    def __init__(self):
        gobject.GObject.__init__(self)
        self.service = UBUNTU_SSO_SERVICE

    def login(self, username=None, password=None):
        if not username or not password:
            self.emit("need-username-password")
            return
        authorizer = BasicHttpAuthorizer(username, password)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        kwargs = { "token_name" : "software-center", }
        self.worker_thread.queue_request(self.SSO_AUTHENTICATE_FUNC, (), kwargs,
                                         self._authentication_done,
                                         self._authentication_error)

    def _authentication_done(self, result):
        print "_authentication_done", result
        self.oauth_credentials = result
        self.emit("login-successful", result)

    def _authentication_error(self, e):
        print "_authentication_error", type(e)
        self.emit("login-failed")

# test code
def _login_success(lp, token):
    print "success", lp, token
def _login_failed(lp):
    print "fail", lp
def _login_need_user_and_password(sso):
    import sys
    sys.stdout.write("user: ")
    sys.stdout.flush()
    user = sys.stdin.readline().strip()
    sys.stdout.write("pass: ")
    sys.stdout.flush()
    password = sys.stdin.readline().strip()
    sso.login(user, password)

def _available_for_me_result(self, scagent, result):
    print "_available_for_me: ", result

def _available(self, scagent, result):
    print "_available_for_me: ", result

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print "need agent or sso as arguemtn"
        sys.exit(1)

    if sys.argv[1] == "agent":
        scagent = SoftwareCenterAgent()
        scagent.connect("available-for-me", _available_for_me_result)
        scagent.connect("available", _available)
        scagent.available_for_me("dummy")

    elif sys.argv[1] == "sso":
        sso = UbuntuSSOlogin()
        sso.connect("login-successful", _login_success)
        sso.connect("login-failed", _login_failed)
        sso.connect("need-username-password", _login_need_user_and_password)
        sso.login()
    else:
        print "unknown option"
        sys.exit(1)


    # wait
    try:
        glib.MainLoop().run()
    except KeyboardInterrupt:
        try:
            sso.worker_thread.shutdown()
        except:
            pass
        try:
            scagent.worker_thread.shutdown()
        except:
            pass
