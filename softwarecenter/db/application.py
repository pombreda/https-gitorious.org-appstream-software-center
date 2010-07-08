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

import apt_pkg
import locale
import os
import re
import string

from apt import Cache
from apt import debfile
from gettext import gettext as _
from mimetypes import guess_type
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
    def __init__(self, appname, pkgname, request, popcon=0):
        if request.count("/") > 0 and not appname:
            self.appname = request.split('/')[-1].split('_')[0].split('.')[0].capitalize()
            self.pkgname = request.split('/')[-1].split('_')[0].split('.')[0].lower()
        else:
            self.pkgname = pkgname
            if appname:
                self.appname = appname
            else:
                self.appname = pkgname.capitalize()
        self.appname = self.appname.replace("$kernel", os.uname()[2])
        self.pkgname = self.pkgname.replace("$kernel", os.uname()[2])
        self.request = request
        if not request:
            if self.pkgname.count("?") > 0:
                self.request = ('?').join(self.pkgname.split('?')[1:])
                self.appname = self.appname.split('?')[0]
                self.pkgname = self.pkgname.split('?')[0]
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
        self._deb = None
        self._error = None
        self._doc = None
        self._pkg = None
        if doc:
            self.init_from_doc(doc)
        elif application:
            self.init_from_application(application)
    def init_from_doc(self, doc):
        """ init the application details from a xapian document """
        self._doc = doc
        self._app = Application(self._db.get_appname(self._doc),
                                self._db.get_pkgname(self._doc),
                                 "")
        self._init_common()
    def init_from_application(self, app):
        """ init the application details from a Application
            class (appname, pkgname, request)
        """
        self._app = app
        self._app.request = self._app.request.replace("$distro", self._distro.get_distro_codename())
        if self._app.request:
            if self._app.request.count('/') > 0:
                self._init_common(deb=True)
                self._init_deb_file()
                return
        try:
            self._doc = self._db.get_xapian_document(self._app.appname, self._app.pkgname)
        except IndexError:
            # check if we have an apturl request to enable a channel
            channel_matches = re.findall(r'channel=[a-z,-]*', self._app.request)
            # check if we have an apturl request to enable a component
            section_matches = re.findall(r'section=[a-z]*', self._app.request)
            # pkg not found (well, we don't have it in app-install data)
            if not channel_matches and not section_matches:
                self._error = _("Not Found") + "@@" + _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
        self._init_common()

    def _init_common(self, deb=False):
        if (self.pkgname in self._cache and 
            self._cache[self.pkgname].candidate):
            self._pkg = self._cache[self.pkgname]
        if not self._pkg and not deb:
            available_for_arch = self._available_for_our_arch()
            if not available_for_arch and (self.channelname or self.component):
                self._error = _("\"%s\" is not available for this type of computer.") % self.name

    def _init_deb_file(self):
        try:
            self._deb = debfile.DebPackage(self._app.request, Cache())
        except (IOError,SystemError),e:
            self._pkg = None
            mimetype = guess_type(self._app.request)
            if (mimetype[0] != None and mimetype[0] != "application/x-debian-package"):
                self._error =  _("Not Found") + '@@' + _("The file \"%s\" is not a software package.") % self._app.request
            else:
                self._error = _("Not Found") + '@@' + _("The file \"%s\" can not be opened. Please check that the file exists and that you have permission to access it.") % self._app.request
        if self._deb:
            # check arch
            if  self.architecture != "all" and self.architecture != get_current_arch():
                self._error = _("The file \"%s\" can not be installed on this type of computer.") %  self._app.request.split('/')[-1]

            # check conflicts and check if installing it would break anything on the current system
            if not self._deb.check_conflicts() or not self._deb.check_breaks_existing_packages():
                self._error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % self._app.request.split('/')[-1]

            # try to satisfy the dependencies
            if not self._deb._satisfy_depends(self._deb.depends):
                self._error = _("The file \"%s\" requires other software packages to be installed that are not available, so can not be installed.") % self._app.request.split('/')[-1]

            # check for conflicts again (this time with the packages that are marked for install)
            if not self._deb.check_conflicts():
                self._error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % self._app.request.split('/')[-1]

    @property
    def architecture(self):
        if self._deb:
            return self._deb._sections["Architecture"]
        if self._doc:
            return self._doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)

    @property
    def channelname(self):
        if self._doc:
            channel = self._doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            path = APP_INSTALL_CHANNELS_PATH + channel + ".list"
            if os.path.exists(path):
                return channel
        else:
            # check if we have an apturl request to enable a channel
            channel_matches = re.findall(r'channel=[a-z,-]*', self._app.request)
            if channel_matches:
                channel = channel_matches[0][8:]
                channelfile = APP_INSTALL_CHANNELS_PATH + channel + ".list"
                if os.path.exists(channelfile):
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
        # then apturl requests
        if not self._doc:
            section_matches = re.findall(r'section=[a-z]*', self._app.request)
            if section_matches:
                valid_section_matches = []
                for section_match in section_matches:
                    if self._unavailable_component(component_to_check=section_match[8:]) and valid_section_matches.count(section_match[8:]) == 0:
                        valid_section_matches.append(section_match[8:])
                if valid_section_matches:
                    return ('&').join(valid_section_matches)

    @property
    def description(self):
        if self._deb:
            description = self._deb._sections["Description"]
            # yeah, below is messy. I'll clean it up or study the parser code
            return ('\n').join(description.split('\n')[1:]).replace(" .\n", "@@@@@").replace("\n", "").replace("@@@@@", "\n\n")
        if self._pkg:
            return self._pkg.candidate.description

    @property
    def error(self):
        # doing this the old way gave massive performance regressions..
        if self._error:
            if self._error.count('@@') > 0:
                return self._error.split('@@')[1]
            else:
                return self._error
        # this may have changed since we inited the appdetails
        if self.pkg_state == PKG_STATE_UNKNOWN:
            self._error =  _("Not Found") + "@@" + _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()

    @property
    def icon(self):
        if self._doc:
            return os.path.splitext(self._db.get_iconname(self._doc))[0]
        if not self.summary:
            return MISSING_PKG_ICON

    @property
    def installation_date(self):
        return self._history.get_installed_date(self.pkgname)

    @property
    def license(self):
        return self._distro.get_license_text(self.component)

    @property
    def maintenance_status(self):
        return self._distro.get_maintenance_status(
            self._cache, self.name, self.pkgname, self.component, 
            self.channelname)

    @property
    def name(self):
        if self.error:
            if self._error.count('@@') > 0:
                return self._error.split('@@')[0]
        return self._app.name

    @property
    def pkg(self):
        if self._pkg:
            return self._pkg

    @property
    def pkgname(self):
        return self._app.pkgname

    @property
    def pkg_state(self):
        if self._deb:
            if self._error:
                return PKG_STATE_UNKNOWN
            else:
                deb_state = self._deb.compare_to_version_in_cache()
                (DEB_NOT_IN_CACHE, DEB_OLDER_THAN_CACHE, DEB_EQUAL_TO_CACHE, DEB_NEWER_THAN_CACHE) = range(4)
                if deb_state == DEB_NOT_IN_CACHE:
                    return PKG_STATE_UNINSTALLED
                elif deb_state == DEB_OLDER_THAN_CACHE:
                    if self._cache[self.pkgname].installed:
                        return PKG_STATE_INSTALLED
                    else:
                        return PKG_STATE_UNINSTALLED
                elif deb_state == DEB_EQUAL_TO_CACHE:
                    return PKG_STATE_REINSTALLABLE
                elif deb_state == DEB_NEWER_THAN_CACHE:
                    if self._cache[self.pkgname].installed:
                        return PKG_STATE_UPGRADABLE
                    else:
                        return PKG_STATE_UNINSTALLED
        if self._pkg:
            # Don't handle upgrades yet
            #if self._pkg.installed and self.pkg._isUpgradable:
            #    return PKG_STATE_UPGRADABLE
            if self._pkg.installed:
                return PKG_STATE_INSTALLED
            else:
                return PKG_STATE_UNINSTALLED
        if not self._pkg and not self._deb:
            if self.channelname and self._unavailable_channel():
                return PKG_STATE_NEEDS_SOURCE
            else:
                if self.component:
                    components = self.component.split('&')
                    for component in components:
                        if (component and (self._unavailable_component(component_to_check=component) or self._available_for_our_arch())):
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
    def summary(self):
        if self._deb:
            description = self._deb._sections["Description"]
            return description.split('\n')[0]
        if self._doc:
            return self._db.get_summary(self._doc)

    @property
    def thumbnail(self):
        return self._distro.SCREENSHOT_THUMB_URL % self.pkgname

    @property
    def version(self):
        if self._deb:
            return self._deb._sections["Version"]
        if self._pkg:
            return self._pkg.candidate.version

    @property
    def warning(self):
        if self._deb:
            deb_state = self._deb.compare_to_version_in_cache()
            (DEB_NOT_IN_CACHE, DEB_OLDER_THAN_CACHE, DEB_EQUAL_TO_CACHE, DEB_NEWER_THAN_CACHE) = range(4)
            if deb_state == DEB_NOT_IN_CACHE:
                return _("Only install deb files if you trust both the author and the distributor.")
            elif deb_state == DEB_OLDER_THAN_CACHE:
                if not self._cache[self.pkgname].installed:
                    return _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.name
            elif deb_state == DEB_EQUAL_TO_CACHE:
                return _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.name
            elif deb_state == DEB_NEWER_THAN_CACHE:
                return _("An older version of \"%s\" is available in your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.name
        # apturl minver matches
        if not self.pkg_state == PKG_STATE_INSTALLED:
            minver_matches = re.findall(r'minver=[a-z,0-9,-,+,.,~]*', self._app.request)
            if minver_matches:
                minver = minver_matches[0][7:]
                if apt_pkg.version_compare(minver, self.version) > 0:
                    return _("Version %s or later is not available from your current software sources.") % minver
        if not self._pkg and not self._deb:
            source_to_enable = None
            if self.channelname and self._unavailable_channel():
                source_to_enable = self.channelname
            elif self.component:
                source_to_enable = self.component
            if source_to_enable:
                sources = source_to_enable.split('&')
                warning = _("This software may be available from the \"%s\" source") % sources[0]
                if len(sources) > 1:
                    for source in sources[1:]:
                       warning += _(", or from the \"%s\" source") % source
                warning += _(", which you are not currently using.")
                return warning

    @property
    def website(self):
        if self._deb:
            website = None
            try:
                website = self._deb._sections["Homepage"]
            except:
                pass
            if website:
                return website
        if self._pkg:
            return self._pkg.candidate.homepage

    def _unavailable_channel(self):
        """ Check if the given doc refers to a channel that is currently not enabled """
        # this is basically just a test to see if canonical-partner is enabled, it won't return true for anything else really..
        channel = self.channelname
        if not channel:
            return False
        if channel.count('-') != 1:
            return False
        available = self._cache.component_available(channel.split('-')[0], channel.split('-')[1])
        return (not available)

    def _unavailable_component(self, component_to_check=None):
        """ Check if the given doc refers to a component that is currently not enabled """
        if component_to_check:
            component = component_to_check
        elif self.component:
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
