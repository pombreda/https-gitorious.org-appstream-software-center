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
import dialogs

import urllib
import gobject

from softwarecenter.db.application import AppDetails
from softwarecenter.db.reviews import get_review_loader
from softwarecenter.backend import get_install_backend
from softwarecenter.enums import *
from softwarecenter.utils import get_current_arch, get_parent_xid, get_default_language

LOG=logging.getLogger(__name__)

class AppDetailsViewBase(object):

    __gsignals__ = {
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, 
                                         gobject.TYPE_PYOBJECT, 
                                         gobject.TYPE_PYOBJECT, 
                                         str,)),
         "purchase-requested" : (gobject.SIGNAL_RUN_LAST,
                                 gobject.TYPE_NONE,
                                 (gobject.TYPE_PYOBJECT,
                                  str,)),
    }

    def __init__(self, db, distro, icons, cache, datadir):
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.datadir = datadir
        self.app = None
        self.appdetails = None
        self.addons_to_install = []
        self.addons_to_remove = []
        # reviews
        self.review_loader = get_review_loader(self.cache)
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
        # gather data
        pkg = self.cache[self.app.pkgname]
        version = pkg.candidate.version
        origin = self.cache.get_origin(self.app.pkgname)
        if pkg.installed:
            version = pkg.installed.version
        # call the loader to do call out the right helper and collect the result
        parent_xid = get_parent_xid(self)
        self.review_loader.spawn_write_new_review_ui(
            self.app, version, self.appdetails.icon, origin,
            parent_xid, self.datadir,
            self._reviews_ready_callback)
                         
    def _review_report_abuse(self, review_id):
        parent_xid = get_parent_xid(self)
        self.review_loader.spawn_report_abuse_ui(
            review_id, parent_xid, self.datadir, self._reviews_ready_callback)

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
        
        self.emit("purchase-requested", self.app, url)

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


