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
import gio
import glib
import logging
import simplejson
import time
import threading

from softwarecenter.distro import get_distro
from softwarecenter.enums import BUY_SOMETHING_HOST, BUY_SOMETHING_HOST_ANONYMOUS
from softwarecenter.utils import get_current_arch, get_default_language

# possible workaround for bug #599332 is to try to import lazr.restful
# import lazr.restful
# import lazr.restfulclient

from lazr.restfulclient.resource import ServiceRoot
from lazr.restfulclient.authorize import BasicHttpAuthorizer
from lazr.restfulclient.authorize.oauth import OAuthAuthorizer
from oauth.oauth import OAuthConsumer, OAuthToken

from softwarecenter.paths import SOFTWARE_CENTER_CACHE_DIR
from Queue import Queue

from login import LoginBackend

UBUNTU_SSO_SERVICE = os.environ.get(
    "USSOC_SERVICE_URL", "https://login.ubuntu.com/api/1.0")

UBUNTU_SOFTWARE_CENTER_AGENT_SERVICE = BUY_SOMETHING_HOST+"/api/1.0"

class EmptyObject(object):
    pass

def restful_collection_to_real_python(restful_list):
    """ take a restful and convert it to a python list with real python
        objects
    """
    l = []
    for entry in restful_list:
        o = EmptyObject()
        for attr in entry.lp_attributes:
            setattr(o, attr, getattr(entry, attr))
        l.append(o)
    return l

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
        self.error = None
        self._logger = logging.getLogger("softwarecenter.backend")
        self._cachedir = os.path.join(SOFTWARE_CENTER_CACHE_DIR,
                                      "restfulclient")

    def run(self):
        """
        Main thread run interface, logs into launchpad
        """
        self._logger.debug("lp worker thread run")
        try:
            self.service = ServiceRoot(self._authorizer, 
                                       self._service_root_url,
                                       self._cachedir)
        except:
            logging.exception("worker thread can not connect to service root")
            self.error = "ERROR_SERVICE_ROOT"
            self._shutdown = True
            return
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
                self._logger.debug("found pending request")
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

class UbuntuSSOAPI(gobject.GObject):

    __gsignals__ = {
        "whoami" : (gobject.SIGNAL_RUN_LAST,
                    gobject.TYPE_NONE, 
                    (gobject.TYPE_PYOBJECT,),
                    ),
        "error" : (gobject.SIGNAL_RUN_LAST,
                    gobject.TYPE_NONE, 
                    (gobject.TYPE_PYOBJECT,),
                    ),

        }
       
    def __init__(self, token):
        gobject.GObject.__init__(self)
        self._whoami = None
        self.service = UBUNTU_SSO_SERVICE
        self.token = token
        token = OAuthToken(self.token["token"], self.token["token_secret"])
        authorizer = OAuthAuthorizer(self.token["consumer_key"],
                                     self.token["consumer_secret"],
                                     access_token=token)
        self.worker_thread =  RestfulClientWorker(authorizer, self.service)
        self.worker_thread.start()
        glib.timeout_add(200, self._monitor_thread)

    def _monitor_thread(self):
        # glib bit of the threading, runs in the main thread
        if self._whoami is not None:
            self.emit("whoami", self._whoami)
            self._whoami = None
        if self.worker_thread.error:
            self.emit("error", self.worker_thread.error)
        return True

    def _thread_whoami_done(self, result):
        self._whoami = result

    def _thread_whoami_error(self, e):
        self.emit("error", e)

    def whoami(self):
        self.worker_thread.queue_request("accounts.me", (), {},
                                         self._thread_whoami_done,
                                         self._thread_whoami_error)


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
        "error" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, 
                   (str,),
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
        if self.worker_thread.error:
            self.emit("error", self.worker_thread.error)
        return True

    def _thread_available_for_me_done(self, result):
        # attributes for each element in the result list:
        # 'application_name', 'archive_id', 'deb_line', 'description', 
        # 'package_name', 'purchase_date', 'purchase_price', 'series', 
        # 'signing_key_id'
        self._available_for_me = restful_collection_to_real_python(result)

    def _thread_available_for_me_error(self, error):
        logging.error("_available_for_me_error %s" % error)
        self._available_for_me = []
        
    def query_available_for_me(self, oauth_token, openid_identifier):
        kwargs = { "oauth_token" : oauth_token,
                   "openid_identifier" : openid_identifier,
                 }
        self.worker_thread.queue_request(self.AVAILABLE_FOR_ME, (), kwargs,
                                         self._thread_available_for_me_done,
                                         self._thread_available_for_me_error)

    def _thread_available_done(self, result):
        logging.debug("_thread_available_done %s %s" % (result,
                      restful_collection_to_real_python(result)))
        self._available = restful_collection_to_real_python(result)

    def _thread_available_error(self, error):
        logging.error("_thread_available_error %s" % error)
        self._available = []

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
        self._oauth_credentials = None
        self._login_failure = None
        self.worker_thread = None

    def shutdown(self):
        self.worker_thread.shutdown()

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
        if self._oauth_credentials:
            self.emit("login-successful", self._oauth_credentials)
            self.oauth_credentials = self._oauth_credentials
            self._oauth_credentials = None
        if self._login_failure:
            self.emit("login-failed")
            self._login_failure = None
        return True

    def _thread_authentication_done(self, result):
        # runs in the thread context, can not touch gui or glib
        print "_authentication_done", result
        self._oauth_credentials = result

    def _thread_authentication_error(self, e):
        # runs in the thread context, can not touch gui or glib
        print "_authentication_error", type(e)
        self._login_failure = e

    def __del__(self):
        print "del"
        if self.worker_thread:
            self.worker_thread.shutdown()

class SoftwareCenterAgentAnonymous(gobject.GObject):
    """ Worker object that does the anonymous communication 
        with the software-center-agent. Fully async and supports
        etags to ensure we don't re-download data we already 
        have
    """

    __gsignals__ = {
        "available" : (gobject.SIGNAL_RUN_LAST,
                              gobject.TYPE_NONE, 
                              (gobject.TYPE_PYOBJECT,),
                             ),
        "error" : (gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, 
                   (str,),
                  ),
        }
    
    def __init__(self):
        gobject.GObject.__init__(self)
        self.distro = get_distro()
        self.log = logging.getLogger("softwarecenter.backend.scagent")
        # make sure we have the cachdir
        if not os.path.exists(SOFTWARE_CENTER_CACHE_DIR):
            os.makedirs(SOFTWARE_CENTER_CACHE_DIR)
        # semantic is "etag for the database we currently use"
        self.etagfile = os.path.join(SOFTWARE_CENTER_CACHE_DIR, "agent.etag")
    def _load_etag(self, etagfile, uri):
        """ take a etagfile path and uri and load the latest etag value
            for that host. If there is none, return a invalid etag (no
            quote) that will never match
        """
        if os.path.exists(etagfile):
            return open(etagfile).read()
        else:
            return "invalid-etag"
    def _save_etag(self, etagfile, etag):
        """ save the given etag in the path provided as etagfile """
        open(etagfile, "w").write(etag)        
    def _download_complete_cb(self, f, result):
        """ callback when gio finished the download """
        try:
            (content, length, etag) = f.load_contents_finish(result)
            # store the etag so that we can send it to the server
            self.latest_etag = etag
            self._save_etag(self.etagfile, etag)
        except glib.GError, e:
            self.log.warn("error in load_contents '%s'" % e)
            self.emit("error", str(e))
            return
        self._decode_result_and_emit_signal(content)
    def _decode_result_and_emit_signal(self, content):
        """ helper that decodes a json string to to python objects
            and emits the result via a gobject signal
        """
        # decode and check if its valid
        try:
            json_list =  simplejson.loads(content)
        except simplejson.JSONDecodeError, e:
            self.emit("error", str(e))
            return
        # all good, convert to real objects and emit available items
        items = []
        for item_dict in json_list:
            o = EmptyObject()
            for (key, value) in item_dict.iteritems():
                setattr(o, key, value)
            items.append(o)
        self.emit("available", items)
    def _query_info_complete_cb(self, f, result):
        """ callback when the query for the etag value is finished """
        try:
            real_result = f.query_info_finish(result)
            etag = real_result.get_etag()
        except glib.GError, e:
            self.log.warn("error in query_info '%s'" % e)
            self.emit("error", str(e))
            return
        # something changed, go for it
        if etag != self.latest_etag:
            self.log.debug("remote etag '%s' != '%s' redownloading" % (
                    etag, self.latest_etag))
            f.load_contents_async(self._download_complete_cb)
        else:
            self.log.debug("etags match (%s == %s), doing nothing" % (
                    etag, self.latest_etag))
            self.emit("available", [])
    def query_available(self):
        """ query what software is available for the current codename/arch 
            Note that this function is async and emits "available" or "error"
            signals when done
        """
        series_name = self.distro.get_codename()
        arch_tag = get_current_arch()
        # the server supports only english for now
        lang = get_default_language()
        url = BUY_SOMETHING_HOST_ANONYMOUS + "/apps/%(lang)s/ubuntu/%(series)s/%(arch)s" % {
            'lang' : lang,
            'series' : series_name,
            'arch' : arch_tag, }
        # load latest etag if available
        self.latest_etag = self._load_etag(self.etagfile, url)
        f = gio.File(url)
        f.query_info_async(gio.FILE_ATTRIBUTE_ETAG_VALUE,
                           self._query_info_complete_cb)

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

def _available(scagent, result):
    print "_available: ", [x.name for x in result]
def _error(scaagent, errormsg):
    print "_error:", errormsg
def _whoami(sso, whoami):
    print "whoami: ", whoami

# interactive test code
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) < 2:
        print "need an argument, one of:  'agent','agent-anon' or 'sso'"
        sys.exit(1)

    if sys.argv[1] == "agent":
        scagent = SoftwareCenterAgent()
        scagent.connect("available-for-me", _available_for_me_result)
        scagent.connect("available", _available)
        # argument is oauth token
        scagent.query_available()
        scagent.query_available_for_me("dummy_oauth", "dummy openid")

    elif sys.argv[1] == "sso":
        def _dbus_maybe_login_successful(ssologin, oauth_result):
            sso = UbuntuSSOAPI(oauth_result)
            sso.connect("whoami", _whoami)
            sso.connect("error", _error)
            sso.whoami()
        from login_sso import LoginBackendDbusSSO
        backend = LoginBackendDbusSSO("", "appname", "login_text")
        backend.connect("login-successful", _dbus_maybe_login_successful)
        backend.login_or_register()

    elif sys.argv[1] == "ssologin":
        ssologin = UbuntuSSOlogin()
        ssologin.connect("login-successful", _login_success)
        ssologin.connect("login-failed", _login_failed)
        ssologin.connect("need-username-password", _login_need_user_and_password)
        ssologin.login()
        
    elif sys.argv[1] == "agent-anon":
        anon_agent = SoftwareCenterAgentAnonymous()
        anon_agent.connect("available", _available)
        anon_agent.connect("error", _error)
        anon_agent.query_available()
        
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
