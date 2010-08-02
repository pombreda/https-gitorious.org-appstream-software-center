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
import urllib
import gobject

from softwarecenter.enums import MISSING_APP_ICON
from softwarecenter.db.application import AppDetails
from softwarecenter.backend import get_install_backend
from softwarecenter.enums import *
from softwarecenter.utils import get_current_arch

from purchasedialog import PurchaseDialog

class AppDetailsViewBase(object):

    __gsignals__ = {
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, str),
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
        # aptdaemon
        self.backend = get_install_backend()
        self._logger = logging.getLogger(__name__)
        
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
        self.emit("selected", self.app)
    # public interface
    def reload(self):
        """ reload the package cache, this goes straight to the backend """
        self.backend.reload()
    def install(self):
        """ install the current application, fire an action request """
        self.emit("application-request-action", self.app, APP_ACTION_INSTALL)
    def remove(self):
        """ remove the current application, , fire an action request """
        self.emit("application-request-action", self.app, APP_ACTION_REMOVE)
    def upgrade(self):
        """ upgrade the current application, fire an action request """
        self.emit("application-request-action", self.app, APP_ACTION_UPGRADE)

    def buy_app(self):
        """ initiate the purchase transaction """
        url = self.distro.PURCHASE_APP_URL % (urllib.urlencode({
                    'archive_id' : self.appdetails.ppaname, 
                    'arch' : get_current_arch() ,
                    }))
        dialog = PurchaseDialog(url=url, app=self.app)
        res = dialog.run()
        dialog.destroy()
        # re-init view if user canceled, otherwise the transactions 
        # will finish it after some time
        if res != gtk.RESPONSE_OK:
            self.show_app(self.app)

    def reinstall_purchased(self):
        """ reinstall a purchased app """
        print "reinstall_purchased",  self.app
        appdetails = self.app.get_details(self.db)
        deb_line = appdetails.deb_line
        signing_key_id = appdetails.signing_key_id
        get_install_backend().add_repo_add_key_and_install_app(deb_line,
                                                               signing_key_id,
                                                               self.app)

    # internal callbacks
    def _on_cache_ready(self, cache):
        # re-show the application if the cache changes, it may affect the
        # current application
        self._logger.debug("on_cache_ready")
        self.show_app(self.app)
