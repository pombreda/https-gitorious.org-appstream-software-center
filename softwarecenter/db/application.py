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
        self._doc = self._db.get_xapian_document(self._app.appgname,
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
    def pkgname(self):
        return self._app.pkgname
    @property
    def appname(self):
        return self._app.appname
    @property
    def channel(self):
        channel = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
        if channel:
            path = APP_INSTALL_CHANNELS_PATH + channel +".list"
            if os.path.exists(path):
                return channel
    @property
    def component (self):
        comp = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        # FIXME: get component from apt 
        #if comp is None:
        return comp
    @property
    def pkg(self):
        return self._pkg
    @property
    def description (self):
        if self._pkg:
            return self._pkg.candidate.description
    @property
    def homepage (self):
        if self._pkg:
            return self._pkg.candidate.homepage
    @property
    def icon(self):
        db_icon = os.path.splitext(self._db.get_iconname(self._doc))[0]
        if not db_icon:
            return MISSING_PKG_ICON
        return db_icon
    @property
    def installed_date(self):
        pass
    @property
    def license(self):
        pass
    @property
    def maintainance_time(self):
        pass
    @property
    def version(self):
        pass
    @property
    def pkg_state (self):
        pass
    @property
    def price (self):
        pass
    @property
    def screenshot(self):
        pass
    @property
    def thumbnail(self):
        pass
    @property
    def title(self):
        pass
    @property
    def subtitle(self):
        pass
    @property
    def error(self):
        pass
    @property
    def warning(self):
        pass




