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
import softwarecenter.ui.gtk3.dialogs as dialogs

from gettext import gettext as _

from softwarecenter.db.application import AppDetails
from softwarecenter.backend.reviews import get_review_loader
from softwarecenter.backend import get_install_backend


LOG=logging.getLogger(__name__)

class AppDetailsViewBase(object):

    def __init__(self, db, distro, icons, cache, datadir):
        self.db = db
        self.distro = distro
        self.icons = icons
        self.cache = cache
        self.backend = get_install_backend()
        self.cache.connect("cache-ready", self._on_cache_ready)
        self.datadir = datadir
        self.app = None
        self.appdetails = None
        self.addons_to_install = []
        self.addons_to_remove = []
        # reviews
        self.review_loader = get_review_loader(self.cache, self.db)
        # aptdaemon

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

        # FIXME: probably want to not display the ui if we can't review it
        if not origin:
            dialogs.error(None, 
                        _("Origin unknown"),
                        _("The origin of the application can not "
                          "be detected. Entering a review is not "
                          "possible."))
            return

        if pkg.installed:
            version = pkg.installed.version
        # call the loader to do call out the right helper and collect the result
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_write_new_review_ui(
            self.app, version, self.appdetails.icon, origin,
            parent_xid, self.datadir,
            self._reviews_ready_callback)
                         
    def _review_report_abuse(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_report_abuse_ui(
            review_id, parent_xid, self.datadir, self._reviews_ready_callback)

    def _review_submit_usefulness(self, review_id, is_useful):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_submit_usefulness_ui(
            review_id, is_useful, parent_xid, self.datadir,
            self._reviews_ready_callback)
            
    def _review_modify(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_modify_review_ui(
            parent_xid, self.appdetails.icon, self.datadir, review_id,
            self._reviews_ready_callback)

    def _review_delete(self, review_id):
        parent_xid = ''
        #parent_xid = get_parent_xid(self)
        self.review_loader.spawn_delete_review_ui(
            review_id, parent_xid, self.datadir, self._reviews_ready_callback)

    # internal callbacks
    def _on_cache_ready(self, cache):
        # re-show the application if the cache changes, it may affect the
        # current application
        LOG.debug("on_cache_ready")
        self.show_app(self.app)


