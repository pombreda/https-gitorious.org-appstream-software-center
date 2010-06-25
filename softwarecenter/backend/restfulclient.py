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

from lazr.restfulclient.resource import ServiceRoot
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer

from paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue

UBUNTU_SSO_SERVICE = "https://login.staging.ubuntu.com/api/1.0"

class RestfulClientWorker(threading.Thread):
    """ a generic worker thread for a lazr.restfulclient """

    def __init__(self, authorizer, service_root):
        """ init the thread """
        threading.Thread.__init__(self)
        self.service = ServiceRoot(authorizer, service_root)
        self._service_root_url = service_root
        self._authorizer = authorizer
        self._pending_requests = Queue()
        self._shutdown = False

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        logging.debug("lp worker thread run")
        # loop
        self._wait_for_commands()

    def shutdown(self):
        """Request shutdown"""
        self._shutdown = True

    def queue_request(self, func, args, kwargs, result_callback):
        """
        queue a (remote) command for execution, the result_callback will
        call with the result_list when done (that function will be
        called async)
        """
        self._pending_requests.put((func, args, kwargs, result_callback))

    def _wait_for_commands(self):
        """internal helper that waits for commands"""
        while True:
            while not self._pending_requests.empty():
                logging.debug("found pending request")
                (func, args, kwargs, result_callback) = self._pending_requests.get()
                # run func async
                res = func(*args, **kwargs)
                # provide result to the callback
                result_callback(res)
                self._pending_requests.task_done()
            # wait a bit
            time.sleep(0.1)
            if (self._shutdown and
                self._pending_requests.empty()):
                return

class UbuntuSSOlogin(gobject.GObject):

    __gsignals__ = {
        "login-successful" : (gobject.SIGNAL_RUN_LAST,
                             gobject.TYPE_NONE, 
                             (),
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
        kwargs = { "token_name":"software-center", }
        self.worker_thread.queue_request(
            self.worker_thread.service.authentications.authenticate, (), kwargs,
            self._authentication_done)

    def _authentication_done(self, result_list):
        print "_authentication_done", result_list

# test code
def _login_success(lp):
    print "success", lp
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    sso = UbuntuSSOlogin()
    sso.connect("login-successful", _login_success)
    sso.connect("login-failed", _login_failed)
    sso.connect("need-username-password", _login_need_user_and_password)
    sso.login()


    # wait
    try:
        glib.MainLoop().run()
    except KeyboardInterrupt:
        sso.worker_thread.shutdown()
