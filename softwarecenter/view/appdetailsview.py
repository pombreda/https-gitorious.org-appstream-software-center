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
import gobject

from softwarecenter.db.application import AppDetails
from softwarecenter.backend import get_install_backend
from softwarecenter.enums import *

class AppDetailsViewBase(object):

    __gsignals__ = {
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT, str),
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
        self.addons_install = []
        self.addons_remove = []
        # aptdaemon
        self.backend = get_install_backend()
        self._logger = logging.getLogger(__name__)
        
    def _draw(self):
        """ draw the current app into the window, maybe the function
            you need to overwrite
        """
        pass
    
    # add-on handling
    def _remove_important(self, list):
        for addon in list:
            try:
                pkg = self.cache[addon]
                if pkg.essential or pkg._pkg.important:
                    list.remove(addon)
                
                rdeps = self.cache.get_installed_rdepends(pkg)
                if len(rdeps) > 0 and list.count(addon) > 0:
                    list.remove(addon)
            except KeyError:
                list.remove(addon)
    
    def _recommended_addons(self, app_details):
        pkg = app_details.pkg
        deps = self.cache.get_depends(pkg)
        recommended = []
        if app_details.pkg_state != PKG_STATE_UNINSTALLED:
            recommended = self.cache.get_recommends(pkg)
        else:
            return recommended # recommended pkgs are auto-installed
        for dep in deps:
            try:
                if len(self.cache.get_rdepends(self.cache[dep])) == 1:
                    # pkg is the only known package that depends on dep
                    recommended += self.cache.get_recommends(self.cache[dep])
            except KeyError:
                pass # FIXME: should we handle that differently?
        self._remove_important(recommended)
        for addon in recommended:
            try: 
                pkg_ = self.cache[addon]
            except KeyError:
                recommended.remove(addon)
            else:
                can_remove = False
                for addon_ in recommended:
                    try:
                        if addon in self.cache.get_provides(self.cache[addon_]) \
                        or addon in self.cache.get_depends(self.cache[addon_]) \
                        or addon in self.cache.get_recommends(self.cache[addon_]):
                            can_remove = True
                            break
                    except KeyError:
                        recommended.remove(addon_)
                        break
                if can_remove or not pkg_.candidate or recommended.count(addon) > 1 \
                or addon == pkg.name:
                    recommended.remove(addon)
        self._remove_important(recommended)
        return recommended
    
    def _suggested_addons(self, app_details):
        pkg = app_details.pkg
        deps = self.cache.get_depends(pkg)
        suggested = self.cache.get_suggests(pkg)
        suggested += self.cache.get_renhances(pkg)
        for dep in deps:
            try:
                if len(self.cache.get_rdepends(self.cache[dep])) == 1:
                    # pkg is the only known package that depends on dep
                    suggested += self.cache.get_suggests(self.cache[dep])
                    suggested += self.cache.get_renhances(self.cache[dep])
            except KeyError:
                pass # FIXME: should we handle that differently?
        self._remove_important(suggested)
        for addon in suggested:
            try: 
                pkg_ = self.cache[addon]
            except KeyError:
                suggested.remove(addon)
            else:
                can_remove = False
                for addon_ in suggested:
                    try:
                        if addon in self.cache.get_provides(self.cache[addon_]) \
                        or addon in self.cache.get_depends(self.cache[addon_]) \
                        or addon in self.cache.get_recommends(self.cache[addon_]):
                            can_remove = True
                    except KeyError:
                        suggested.remove(addon_)
                if can_remove or not pkg_.candidate or suggested.count(addon) > 1 \
                or addon == pkg.name:
                    suggested.remove(addon)
        self._remove_important(suggested)
        return suggested
        
    def _set_addon_install(self, addon):
        pkg = self.cache[addon]
        if addon not in self.addons_install and pkg.installed == None:
            self.addons_install.append(addon)
        if addon in self.addons_remove:
            self.addons_remove.remove(addon)
    
    def _set_addon_remove(self, addon):
        pkg = self.cache[addon]
        if addon not in self.addons_remove and pkg.installed != None:
            self.addons_remove.append(addon)
        if addon in self.addons_install:
            self.addons_install.remove(addon)
        
    # public API
    def show_app(self, app):
        """ show the given application """
        if app is None:
            return
        self.app = app
        self.appdetails = AppDetails(self.db, application=app)
        self._draw()
        self.emit("selected", self.app)
    # public interface
    def reload(self):
        """ reload the package cache, this goes straight to the backend """
        self.backend.reload()
    def install(self):
        """ install the current application, fire an action request """
        self.emit("application-request-action", self.app, self.addons_install, self.addons_remove, APP_ACTION_INSTALL)
    def remove(self):
        """ remove the current application, , fire an action request """
        self.emit("application-request-action", self.app, self.addons_install, self.addons_remove, APP_ACTION_REMOVE)
    def upgrade(self):
        """ upgrade the current application, fire an action request """
        self.emit("application-request-action", self.app, self.addons_install, self.addons_remove, APP_ACTION_UPGRADE)
    def apply_changes(self):
        """ apply changes concerning add-ons """
        self.emit("application-request-action", self.app, self.addons_install, self.addons_remove, APP_ACTION_APPLY)
    # internal callbacks
    def _on_cache_ready(self, cache):
        # re-show the application if the cache changes, it may affect the
        # current application
        self._logger.debug("on_cache_ready")
        self.show_app(self.app)
