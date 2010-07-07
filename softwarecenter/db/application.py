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

import locale
import os

from softwarecenter.distro import get_distro
from softwarecenter.apt.apthistory import get_apt_history
from softwarecenter.enums import *

class Application(object):
    """ The central software item abstraction. it conaints a 
        pkgname that is always available and a optional appname
        for packages with multiple applications
        
        There is also a __cmp__ method and a name property
    """
    def __init__(self, appname, pkgname, popcon=0):
        self.appname = appname
        self.pkgname = pkgname
        self._popcon = popcon
    @property
    def name(self):
        """Show user visible name"""
        if self.appname:
            return self.appname
        return self.pkgname
    @property
    def popcon(self):
        return self._popcon
    # special methods
    def __hash__(self):
        return ("%s:%s" % (self.appname, self.pkgname)).__hash__()
    def __cmp__(self, other):
        return self.apps_cmp(self, other)
    def __str__(self):
        return "%s,%s" % (self.appname, self.pkgname)
    @staticmethod
    def apps_cmp(x, y):
        """ sort method for the applications """
        # sort(key=locale.strxfrm) would be more efficient, but its
        # currently broken, see http://bugs.python.org/issue2481
        if x.appname and y.appname:
            return locale.strcoll(x.appname, y.appname)
        elif x.appname:
            return locale.strcoll(x.appname, y.pkgname)
        elif y.appname:
            return locale.strcoll(x.pkgname, y.appname)
        else:
            return cmp(x.pkgname, y.pkgname)

class AppDetails(object):
    """ The details for a Application. This contains all the information
        we have available like homepage url etc
    """

    def __init__(self, db, doc=None, application=None):
        """ Create a new AppDetails object. It can be created from
            a xapian.Document or from a db.application.Application object
        """
        if not doc and not application:
            raise ValueError, "Need either document or application"
        self._db = db
        self._cache = self._db._aptcache
        self._distro = get_distro()
        self._history = get_apt_history()
        if doc:
            self.init_from_doc(doc)
        elif application:
            self.init_from_application(application)
    def init_from_doc(self, doc):
        self._doc = doc
        self._app = Application(self._db.get_appname(self._doc),
                                self._db.get_pkgname(self._doc))
        self._init_common()
    def init_from_application(self, app):
        self._app = app
        self._doc = self._db.get_xapian_document(self._app.appname,
                                                 self._app.pkgname)
        if not self._doc:
            raise IndexError, "No app '%s' for '%s' in database" % (
                self._app.appname, self._app.pkgname)
        self._init_common()
    def _init_common(self):
        if (self.pkgname in self._cache and 
            self._cache[self.pkgname].candidate):
            self._pkg = self._cache[self.pkgname]

    @property
    def architecture(self):
        # arches isn't quite as explicit as architecture, feel free to revert
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)

    @property
    def channel(self):
        if self._doc:
            channel = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            if channel:
                path = APP_INSTALL_CHANNELS_PATH + channel +".list"
                if os.path.exists(path):
                    return channel

    @property
    def component(self):
        if self._doc:
            comp = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
            # FIXME: get component from apt 
            #if comp is None:
            return comp

    @property
    def description(self):
        if self._pkg:
            return self._pkg.candidate.description

    @property
    def error(self):
        pass

    @property
    def icon(self):
        if self._doc:
            return os.path.splitext(self._db.get_iconname(self._doc))[0]
        # the missing app icon code I removed here should probably be in the appdetailsview code

    @property
    def installation_date(self):
        return self._history.get_installed_date(self.pkgname)

    @property
    def license(self):
        return self._distro.get_license_text(self.component)

    @property
    def maintenance_status(self):
        return self._distro.get_maintenance_status(
            self._cache, self.appname, self.pkgname, self.component, 
            self.channel)

    @property
    def name(self):
        # I changed this from appname to name, as appdetails.appname seems a bit repetitive, if you want to change it back, feel free
        return self._app.appname

    @property
    def pkg(self):
        if self._pkg:
            return self._pkg

    @property
    def pkgname(self):
        return self._app.pkgname

    @property
    def pkg_state(self):
        pass

    @property
    def price(self):
        if self._doc:
            return self._distro.get_price(self._doc)

    @property
    def screenshot(self):
        return self._distro.SCREENSHOT_LARGE_URL % self.pkgname

    @property
    def summary(self):
        if self._doc:
            return self._db.get_summary(self._doc)

    @property
    def thumbnail(self):
        return self._distro.SCREENSHOT_THUMB_URL % self.pkgname

    @property
    def version(self):
        if self._pkg:
            return self._pkg.candidate.version

    @property
    def warning(self):
        pass

    @property
    def website(self):
    # I think the term website is a bit more common than the term homepage, feel free to revert
        if self._pkg:
            return self._pkg.candidate.homepage
