# Copyright (C) 2009-2010 Canonical
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

import apt
import apt_pkg
import os

from apt import Cache
from apt import debfile
from gettext import gettext as _
from mimetypes import guess_type
from softwarecenter.enums import *
from softwarecenter.utils import *

class ApplicationDetails(object):
    """ This is a centralised place for all application details """
    def __init__(self, cache, db, distro, history, icons, app):

        self._cache = cache
        self._db = db
        self._distro = distro
        self._history = history
        self._icons = icons
        self._request = app.request

        self.pkgname = app.pkgname

        self.channel = None
        self.component = None
        self.description = None
        self.error = None
        self.homepage = None
        self.icon = MISSING_APP_ICON
        self.installed_date = self._history.get_installed_date(self.pkgname)
        self.license = None
        self.maintainance_time = None
        self.pkg = None
        self.price = None
        self.screenshot = self._distro.SCREENSHOT_LARGE_URL % self.pkgname
        self.status = None
        self.subtitle = None
        self.thumbnail = self._distro.SCREENSHOT_THUMB_URL % self.pkgname
        self.type = None
        self.title = app.appname
        self.version = None
        self.warning = None

        if self._request.count('/') > 0:
            self.init_deb_file()
        else:
            self.init_pkg()

    def init_pkg(self):
        try:
            self.doc = self._db.get_xapian_document(self.title, self.pkgname)
        except IndexError:
            # pkg not found (well, we don't have it in app-install data)
            self.error = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
            self.icon = MISSING_PKG_ICON
            self.title = _("Not Found")
            return

        # pkg may or may not be in cache
        db_icon = os.path.splitext(self._db.get_iconname(self.doc))[0]
        if self._icons.has_icon(db_icon):
            self.icon = db_icon
        self.price = self._distro.get_price(self.doc)
        self.subtitle = self._db.get_summary(self.doc)

        # check if pkg in cache
        self.pkg = None
        if (self.pkgname in self._cache and self._cache[self.pkgname].candidate):
            self.pkg = self._cache[self.pkgname]

        # do stuff depending on above
        if self.pkg:
            self.pkg_in_cache()
        else:
            self.pkg_not_in_cache()

        # post decision stuff
        self.license = self._distro.get_license_text(self.component).split()[1]
        self.channelfile = None
        self.maintainance_time = self._distro.get_maintenance_status(self._cache, self.title or self.pkgname, self.pkgname, self.component, self.channelfile)
        self.check_for_apturl_minver()

    def pkg_in_cache(self):
        self.homepage_url = self.pkg.candidate.homepage
        self.version = self.pkg.candidate.version
        for origin in self.pkg.candidate.origins:
            if (origin.origin == "Ubuntu" and origin.trusted and origin.component):
                self.component =  origin.component
        self.description = self.pkg.candidate.description
        # Don't handle upgrades yet
        #if self.pkg.installed and self.pkg.isUpgradable:
        #    return PKG_STATE_UPGRADABLE
        if self.pkg.installed:
            self.status = PKG_STATE_INSTALLED
        else:
            self.status = PKG_STATE_UNINSTALLED

    def pkg_not_in_cache(self):
        self.component = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        self.channelname = None
        channel = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
        if channel:
            path = APP_INSTALL_CHANNELS_PATH + channel +".list"
            if os.path.exists(path):
                self.channelname = channel
                self.channelfile = path
                ## FIXME: deal with the EULA stuff
                self.status = PKG_STATE_NEEDS_SOURCE
        available_for_arch = self._available_for_our_arch()
        if not available_for_arch and (self.channelname or self.component):
            self.error = _("\"%s\" is not available for this type of computer.") % self.title
        if self.channelname:
            self.warning = _("\"%s\" is available from the \"%s\" source, "
                         "which you are not currently using.") % (self.title, self.channelname)
        if self.component:
            self.warning = _("To show information about this item, the software catalog needs updating.")
        if not channel:
            if self._unavailable_component():
                self.status = PKG_STATE_UNAVAILABLE
            elif self._available_for_our_arch():
                self.status = PKG_STATE_NEEDS_SOURCE


### deb file stuff ###
    def init_deb_file(self):
        """ Initialise a deb file """
        try:
            deb = debfile.DebPackage(self._request, Cache())
        except (IOError,SystemError),e:
            mimetype = guess_type(self._request)
            if (mimetype[0] != None and mimetype[0] != "application/x-debian-package"):
                self.error = _("The file \"%s\" is not a software package.") % self._request
                self.icon = MISSING_PKG_ICON
                self.title = _("Not Found")
                return  
            else:
                self.error = _("The file \"%s\" can not be opened. Please check that the file exists and that you have permission to access it.") % self._request
                self.icon = MISSING_PKG_ICON
                self.title = _("Not Found")
                return

        # info from control file
        description = deb._sections["Description"]
        self.description = ('\n').join(description.split('\n')[1:]).replace(" .\n", "@@@@@").replace("\n", "").replace("@@@@@", "\n\n")
        try:
            self.homepage = deb._sections["Homepage"]
        except:
            pass
        self.subtitle = description.split('\n')[0]
        self.title = self.pkgname.capitalize()
        self.type = "deb-file"
        self.version = deb._sections["Version"]

        # additional info from app-install desktop file
        # FIXME: use xapian for this again..
        desktop_file_path = APP_INSTALL_DESKTOP_PATH + self.pkgname + '.desktop'
        if os.path.exists(desktop_file_path):
            desktop_file = open(desktop_file_path, 'r')
            for line in desktop_file.readlines():
                if line[:5] == "Name=": 
                    #FIXME: different languages?
                    self.title = line[5:].strip('\n')
                if line[:5] == "Icon=":
                    db_icon = line[5:].strip('\n')
                    if self._icons.has_icon(db_icon):
                        self.icon = db_icon
            desktop_file.close()

        # get errors and warnings
        self.check_deb_file_for_errors(deb)
        self.set_status_for_deb_files(deb.compare_to_version_in_cache())

    def check_deb_file_for_errors(self, deb):
        """ Set error messages for deb files """
        # check arch
        arch = deb._sections["Architecture"]
        if  arch != "all" and arch != get_current_arch():
            self.error = _("The file \"%s\" can not be installed on this type of computer.") %  self._request.split('/')[-1]

        # check conflicts and check if installing it would break anything on the current system
        if not deb.check_conflicts() or not deb.check_breaks_existing_packages():
            self.error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % self._request.split('/')[-1]

        # try to satisfy the dependencies
        if not deb._satisfy_depends(deb.depends):
            self.error = _("The file \"%s\" requires other software packages to be installed that are not available, so can not be installed.") % self._request.split('/')[-1]

        # check for conflicts again (this time with the packages that are marked for install)
        if not deb.check_conflicts():
            self.error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % self._equest.split('/')[-1]

    def set_status_for_deb_files(self, version_status):
        """ Set status and warning for deb files """
        if self.error:
            self.status = PKG_STATE_UNKNOWN
        else:
            (DEB_NOT_IN_CACHE, DEB_OLDER_THAN_CACHE, DEB_EQUAL_TO_CACHE, DEB_NEWER_THAN_CACHE) = range(4)
            if version_status == DEB_NOT_IN_CACHE:
                self.status = PKG_STATE_UNINSTALLED
                self.warning = _("Only install deb files if you trust both the author and the distributor.")
            elif version_status == DEB_OLDER_THAN_CACHE:
                if self._cache[self.pkgname].installed:
                    self.status = PKG_STATE_INSTALLED
                else:
                    self.status = PKG_STATE_UNINSTALLED
                    self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
            elif version_status == DEB_EQUAL_TO_CACHE:
                self.status = PKG_STATE_REINSTALLABLE
                self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
            elif version_status == DEB_NEWER_THAN_CACHE:
                if self._cache[self.pkgname].installed:
                    self.status = PKG_STATE_UPGRADABLE
                else:
                    self.status = PKG_STATE_UNINSTALLED
                self.warning = _("An older version of \"%s\" is available in your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title

    def _unavailable_component(self):
        """ Check if the given doc refers to a component that is currently not enabled """
        # FIXME: use self.component here instead?
        component =  self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        if not component:
            return False
        distro_codename = self._distro.get_codename()
        available = self._cache.component_available(distro_codename, component)
        return (not available)

    def _available_for_our_arch(self):
        """ check if the given package is available for our arch """
        arches = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_ARCH)
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

    def check_for_apturl_minver(self):
        """ Insert warning if apturl minver requirements are not met """
        if self._request[:7] == "minver=":
            minver = self._request[7:]
            if apt_pkg.version_compare(minver, self.version) > 0:
                self.warning = _("Version %s or later is not available from your current software sources.") % minver
