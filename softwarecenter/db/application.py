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

import locale
import os
import string

from gettext import gettext as _
from softwarecenter.apt.apthistory import get_apt_history
from softwarecenter.distro import get_distro
from softwarecenter.enums import *
from softwarecenter.utils import *

# this is a very lean class as its used in the main listview
# and there are a lot of application objects in memory
class Application(object):
    """ The central software item abstraction. it contains a 
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
        return self.pkgname.capitalize()
    @property
    def popcon(self):
        return self._popcon
    # get a AppDetails object for this Applications
    def get_details(self, db):
        """ return a new AppDetails object for this application """
        return AppDetails(db, application=self)
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

# the details
class AppDetails(object):
    """ The details for a Application. This contains all the information
        we have available like website etc
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
        """ init the application details from a xapian document """
        self._doc = doc
        self._app = Application(self._db.get_appname(self._doc),
                                self._db.get_pkgname(self._doc),)
        self._init_common()
    def init_from_application(self, app):
        """ init the application details from a Application
            class (appname, pkgname)
        """
        self._app = app
        try:
            self._doc = self._db.get_xapian_document(self._app.appname, self._app.pkgname)
        except IndexError:
            self._doc = None
            self._app = Application("Not Found", app.pkgname)
        self._init_common()
    def _init_common(self):
        self._pkg = None
        if (self.pkgname in self._cache and 
            self._cache[self.pkgname].candidate):
            self._pkg = self._cache[self.pkgname]

    @property
    def architecture(self):
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)

    @property
    def channelname(self):
        if self._doc:
            channel =  self._doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            path = APP_INSTALL_CHANNELS_PATH + channel + ".list"
            if os.path.exists(path):
                return channel

    @property
    def channelfile(self):
        channel = self.channelname
        if channel:
            return APP_INSTALL_CHANNELS_PATH + channel + ".list"

    @property
    def component(self):
        """ 
        get the component (main, universe, ..)
        
        this uses the data from apt, if there is none it uses the 
        data from the app-install-data files
        """
        # try apt first
        if self._pkg:
            for origin in self._pkg.candidate.origins:
                if (origin.origin == "Ubuntu" and origin.trusted and origin.component):
                    return origin.component
        # then xapian
        if self._doc:
            comp = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
            return comp

    @property
    def description(self):
        if self._pkg:
            return self._pkg.candidate.description

    @property
    def error(self):
        if not self._pkg:
            available_for_arch = self._available_for_our_arch()
            if not available_for_arch and (self.channelname or self.component):
                return _("\"%s\" is not available for this type of computer.") % self.name
        if not self.summary:
            return _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()

    @property
    def icon(self):
        if self._doc:
            return os.path.splitext(self._db.get_iconname(self._doc))[0]
        if not self.summary:
            return MISSING_PKG_ICON
            
    @property
    def icon_file_name(self):
        if self._doc:
            return self._db.get_iconname(self._doc)
            
    @property
    def icon_needs_download(self):
        if self._doc:
            return self._db.get_icon_needs_download(self._doc)

    @property
    def installation_date(self):
        return self._history.get_installed_date(self.pkgname)

    @property
    def license(self):
        return self._distro.get_license_text(self.component)

    @property
    def maintenance_status(self):
        return self._distro.get_maintenance_status(
            self._cache, self.display_name, self.pkgname, self.component, 
            self.channelname)

    @property
    def name(self):
        return self._app.name
    
    @property
    def display_name(self):
        """ Return the name as it should be displayed in the UI

            Note that this may not corespond to the Appname as the
            spec says the name should be the summary for packages
            and the summary the pkgname
        """
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return name
            else:
                # by spec..
                return self._db.get_summary(self._doc)
        return self.name

    @property
    def display_summary(self):
        """ Return the summary as it should be displayed in the UI

            Note that this may not corespond to the summary value as the
            spec says the name should be the summary for packages
            and the summary the pkgname
        """
        if self._doc:
            name = self._db.get_appname(self._doc)
            if name:
                return self._db.get_summary(self._doc)
            else:
                # by spec..
                return self._db.get_pkgname(self._doc)

    @property
    def pkg(self):
        if self._pkg:
            return self._pkg

    @property
    def pkgname(self):
        return self._app.pkgname

    @property
    def pkg_state(self):
        if self._pkg:
            # Don't handle upgrades yet
            #if self._pkg.installed and self.pkg._isUpgradable:
            #    return PKG_STATE_UPGRADABLE
            if self._pkg.installed:
                return PKG_STATE_INSTALLED
            else:
                return PKG_STATE_UNINSTALLED
        if not self._pkg:
            if self.channelname or (not self.channelname and self.component and (self._unavailable_component() or self._available_for_our_arch())):
                return PKG_STATE_NEEDS_SOURCE
        return PKG_STATE_UNKNOWN

    @property
    def price(self):
        if self._doc:
            return self._distro.get_price(self._doc)

    @property
    def screenshot(self):
        return self._distro.SCREENSHOT_LARGE_URL % self.pkgname
        
    @property
    def screenshot_url(self):
        if self._doc:
            return self._db.get_screenshot_url(self._doc)

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
        if not self._pkg:
            source = None
            if self.channelname:
                source = self.channelname
            elif self.component:
                source = self.component
            if source:
                return _("This software is available from the \"%s\" source, which you are not currently using.") % source

    @property
    def website(self):
        if self._pkg:
            return self._pkg.candidate.homepage

    def _unavailable_component(self):
        """ Check if the given doc refers to a component that is currently not enabled """
        if self.component:
            component = self.component
        else:
            component =  self._doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        if not component:
            return False
        distro_codename = self._distro.get_codename()
        available = self._cache.component_available(distro_codename, component)
        return (not available)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.architecture
        # if we don't have a arch entry in the document its available
        # on all architectures we know about
        if not arches:
            return True
        # check the arch field and support both "," and ";"
        sep = ","
        if ";" in arches:
            sep = ";"
        elif "," in arches:
            sep = ","
        for arch in map(string.strip, arches.split(sep)):
            if arch == get_current_arch():
                return True
        return False
