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


import logging
import gtk

import json
import logging
import os
import re
import glib
import simplejson
import socket
import string
import subprocess
import sys
import tempfile

import urllib
import gobject

from softwarecenter.db.application import AppDetails
from softwarecenter.db.reviews import get_review_loader
from softwarecenter.backend import get_install_backend
from softwarecenter.enums import *
from softwarecenter.utils import get_current_arch, get_parent_xid, get_default_language

from softwarecenter.backend.rnrclient import RatingsAndReviewsAPI, ReviewRequest, ReviewDetails

from purchasedialog import PurchaseDialog

LOG=logging.getLogger(__name__)

class AppDetailsViewBase(object):

    __gsignals__ = {
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, 
                                         gobject.TYPE_PYOBJECT, 
                                         gobject.TYPE_PYOBJECT, 
                                         str),
                                       ),
    }

    def __init__(self, db, distro, icons, cache, history, datadir):
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.history = history
        self.datadir = datadir
        self.app = None
        self.appdetails = None
        self.addons_to_install = []
        self.addons_to_remove = []
        # reviews
        self.review_loader = get_review_loader()
        # aptdaemon
        self.backend = get_install_backend()
        
    def _draw(self):
        """ draw the current app into the window, maybe the function
            you need to overwrite
        """
        pass
    # public API
    def show_app(self, app):
        """ show the given application """
        if app is None:
            return
        self.app = app
        self.appdetails = AppDetails(self.db, application=app)
        #print "AppDetailsViewWebkit:"
        #print self.appdetails
        self._draw()
        self._check_for_reviews()
        self.emit("selected", self.app)
    def refresh_app(self):
        self.show_app(self.app)

    # common code
    def _review_write_new(self):
        if (not self.app or
            not self.app.pkgname in self.cache or
            not self.cache[self.app.pkgname].candidate):
            dialogs.error(None, 
                          _("Version unknown"),
                          _("The version of the application can not "
                            "be detected. Entering a review is not "
                            "possible."))
            return
        # call out
        pkg = self.cache[self.app.pkgname]
        version = pkg.candidate.version
        if pkg.installed:
            version = pkg.installed.version
        cmd = [os.path.join(self.datadir, SUBMIT_REVIEW_APP), 
               "--pkgname", self.app.pkgname,
               "--iconname", self.appdetails.icon,
               "--parent-xid", "%s" % get_parent_xid(self),
               "--version", version,
               "--datadir", self.datadir,
               ]
        if self.app.appname:
            cmd += ["--appname", self.app.appname]
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD, standard_output=True)
        glib.child_watch_add(pid, self.on_submit_review_finished, stdout)
                         
    def _review_report_abuse(self, review_id):
        cmd = [os.path.join(self.datadir, REPORT_REVIEW_APP), 
               "--review-id", review_id,
               "--parent-xid", "%s" % get_parent_xid(self),
               "--datadir", self.datadir,
              ]
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD, standard_output=True)
        glib.child_watch_add(pid, self.on_report_abuse_finished, stdout)

    def on_report_abuse_finished(self, pid, status, stdout_fd):
        """ called when report_absuse finished """
        stdout = ""
        while True:
            s = os.read(stdout_fd, 1024)
            if not s: break
            stdout += s
        LOG.debug("stdout from report_abuse: '%s'" % stdout)

    def on_submit_review_finished(self, pid, status, stdout_fd):
        """ called when submit_review finished """
        #print"on_submit_finished",  pid, os.WEXITSTATUS(status)
        # read stdout from submit_review
        stdout = ""
        while True:
            s = os.read(stdout_fd, 1024)
            if not s: break
            stdout += s
        LOG.debug("stdout from submit_review: '%s'" % stdout)
        if os.WEXITSTATUS(status) == 0:
            review = simplejson.loads(stdout)
            if hasattr(self, "reviews"):
                self.reviews.add_review(ReviewDetails.from_dict(review))
                self.reviews.finished()

    # public interface
    def reload(self):
        """ reload the package cache, this goes straight to the backend """
        self.backend.reload()
    def install(self):
        """ install the current application, fire an action request """
        self.emit("application-request-action", self.app, self.addons_to_install, self.addons_to_remove, APP_ACTION_INSTALL)
    def remove(self):
        """ remove the current application, , fire an action request """
        self.emit("application-request-action", self.app, self.addons_to_install, self.addons_to_remove, APP_ACTION_REMOVE)
    def upgrade(self):
        """ upgrade the current application, fire an action request """
        self.emit("application-request-action", self.app, self.addons_to_install, self.addons_to_remove, APP_ACTION_UPGRADE)
    def apply_changes(self):
        """ apply changes concerning add-ons """
        self.emit("application-request-action", self.app, self.addons_to_install, self.addons_to_remove, APP_ACTION_APPLY)

    def buy_app(self):
        """ initiate the purchase transaction """
        lang = get_default_language()
        url = self.distro.PURCHASE_APP_URL % (lang, urllib.urlencode({
                    'archive_id' : self.appdetails.ppaname, 
                    'arch' : get_current_arch() ,
                    }))
        appdetails = self.app.get_details(self.db)
        self.purchase_dialog = PurchaseDialog(url=url, 
                                              app=self.app,
                                              iconname=appdetails.icon)
        res = self.purchase_dialog.run()
        self.purchase_dialog.destroy()
        del self.purchase_dialog
        # re-init view if user canceled, otherwise the transactions 
        # will finish it after some time
        if res != gtk.RESPONSE_OK:
            self.show_app(self.app)

    def reinstall_purchased(self):
        """ reinstall a purchased app """
        LOG.debug("reinstall_purchased %s" % self.app)
        appdetails = self.app.get_details(self.db)
        iconname = appdetails.icon
        deb_line = appdetails.deb_line
        signing_key_id = appdetails.signing_key_id
        get_install_backend().add_repo_add_key_and_install_app(deb_line,
                                                               signing_key_id,
                                                               self.app,
                                                               iconname)

    # internal callbacks
    def _on_cache_ready(self, cache):
        # re-show the application if the cache changes, it may affect the
        # current application
        LOG.debug("on_cache_ready")
        self.show_app(self.app)


