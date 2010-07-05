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
from softwarecenter.utils import get_current_arch

# possible workaround for bug #599332 is to try to import lazr.restful
# import lazr.restful
# import lazr.restfulclient

from lazr.restfulclient.resource import ServiceRoot
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthConsumer, OAuthToken

from paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue

from login import LoginBackend

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
        self.daemon = True

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
        # distro
        self.distro = get_distro()
        # data
        self._available = None
        self._available_for_me = None
        # setup restful client
        self.service = UBUNTU_SOFTWARE_CENTER_AGENT_SERVICE
        empty_token = OAuthToken("", "")
        authorizer = OAuthAuthorizer("software-center", access_token=empty_token)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        glib.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self._available is not None:
            self.emit("available", self._available)
            self._available = None
        if self._available_for_me is not None:
            self.emit("available-for-me", self._available_for_me)
            self._available_for_me = None
        return True

    def _thread_available_for_me_done(self, result):
        print "_availalbe_for_me_done"
        self._available_for_me =  [x for x in result]

    def _thread_available_for_me_error(self, error):
        print "_available_for_me_error:", error
        
    def query_available_for_me(self, oauth_token, openid_identifier):
        kwargs = { "oauth_token" : oauth_token,
                   "openid_identifier" : openid_identifier,
                 }
        self.worker_thread.queue_request(self.AVAILABLE_FOR_ME, (), kwargs,
                                         self._thread_available_for_me_done,
                                         self._thread_available_for_me_error)

    def _thread_available_done(self, result):
        print "_availalbe", result
        self._available = [x for x in result]

    def _thread_available_error(self, error):
        print "available_error: ", error

    def query_available(self, series_name=None, arch_tag=None):
        if not series_name:
            series_name = self.distro.get_codename()
        if not arch_tag:
            arch_tag = get_current_arch()
        kwargs = { "series_name" : series_name,
                   "arch_tag" : arch_tag,
                 }
        self.worker_thread.queue_request(self.AVAILABLE, (), kwargs,
                                         self._thread_available_done,
                                         self._thread_available_error)


class UbuntuSSOlogin(LoginBackend):

    NEW_ACCOUNT_URL = "https://login.launchpad.net/+standalone-login"
    FORGOT_PASSWORD_URL = "https://login.ubuntu.com/+forgot_password"

    SSO_AUTHENTICATE_FUNC = "authentications.authenticate"

    def __init__(self):
        LoginBackend.__init__(self)
        self.service = UBUNTU_SSO_SERVICE
        # we get a dict here with the following keys:
        #  token
        #  consumer_key (also the openid identifier)
        #  consumer_secret
        #  token_secret
        #  name (that is just 'software-center')
        self.oauth_credentials = None
        self._login_failure = None

    def login(self, username=None, password=None):
        if not username or not password:
            self.emit("need-username-password")
            return
        authorizer = BasicHttpAuthorizer(username, password)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        kwargs = { "token_name" : "software-center", 
                 }
        self.worker_thread.queue_request(self.SSO_AUTHENTICATE_FUNC, (), kwargs,
                                         self._thread_authentication_done,
                                         self._thread_authentication_error)
        glib.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self.oauth_credentials:
            self.emit("login-successful", result)
        if self._login_failure:
            self.emit("login-failed")
            self._login_failure = None
        return True

    def _thread_authentication_done(self, result):
        # runs in the thread context, can not touch gui or glib
        print "_authentication_done", result
        self.oauth_credentials = result

    def _thread_authentication_error(self, e):
        # runs in the thread context, can not touch gui or glib
        print "_authentication_error", type(e)
        self._login_failure = e

    def __del__(self):
        print "del"
        self.worker_thread.shutdown()

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

def _available_for_me_result(scagent, result):
    print "_available_for_me: ", [x.package_name for x in result]

def _available( scagent, result):
    print "_available: ", [x.name for x in result]

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
        # argument is oauth token
        scagent.query_available_for_me("dummy_oauth")
        scagent.query_available()

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
