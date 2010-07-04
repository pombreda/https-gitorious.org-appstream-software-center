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
import os

from apt import Cache
from apt import debfile
from gettext import gettext as _
from mimetypes import guess_type
from softwarecenter.enums import *
from softwarecenter.utils import *

PKG_STATE_INSTALLED     = 0
PKG_STATE_UNINSTALLED   = 1
PKG_STATE_UPGRADABLE    = 2
PKG_STATE_INSTALLING    = 3
PKG_STATE_REMOVING      = 4
PKG_STATE_UPGRADING     = 5
PKG_STATE_NEEDS_SOURCE  = 6
PKG_STATE_UNAVAILABLE   = 7
PKG_STATE_UNKNOWN       = 8
PKG_STATE_REINSTALLABLE = 9

class ApplicationDetails(object):
    """ This is a centralised place for all application details """
    def __init__(self, cache, db, distro, history, app):

        self.cache = cache
        self.db = db
        self.distro = distro
        self.history = history
        self.request = app.request

        self.description = None
        self.error = None
        self.homepage = None
        self.icon = MISSING_APP_ICON
        self.installed_date = None
        self.license = None
        self.maintainance_time = None
        self.pkgname = app.pkgname
        self.price = None
        self.screenshot_small = None
        self.screenshot_large = None
        self.status = None
        self.subtitle = None
        self.type = None
        self.title = app.appname
        self.version = None
        self.warning = None

        if self.request:
            if self.request.count('/') > 0:
                # deb file


                # Constants for comparing the local package file with the version in the cache
                (DEB_NOT_IN_CACHE, DEB_OLDER_THAN_CACHE, DEB_EQUAL_TO_CACHE, DEB_NEWER_THAN_CACHE) = range(4)

                # open the package
                try:
                    deb = debfile.DebPackage(self.request, Cache())
                except (IOError,SystemError),e:
                    mimetype = guess_type(self.request)
                    if (mimetype[0] != None and mimetype[0] != "application/x-debian-package"):
                        self.error = _("The file \"%s\" is not a software package.") % self.request
                        self.icon = MISSING_PKG_ICON
                        self.title = _("Not Found")
                        return  
                    else:
                        self.error = _("The file \"%s\" can not be opened. Please check that the file exists and that you have permission to access it.") % self.request
                        self.icon = MISSING_PKG_ICON
                        self.title = _("Not Found")
                        return

                # do some stuff
                description = deb._sections["Description"]

                # set variables
                self.description = ('\n').join(description.split('\n')[1:]).replace(" .\n", "@@@@@").replace("\n", "").replace("@@@@@", "\n\n")
                try:
                    self.homepage = deb._sections["Homepage"]
                except:
                    pass
                self.subtitle = description.split('\n')[0]
                self.title = self.pkgname.capitalize()
                self.type = "deb-file"
                self.version = deb._sections["Version"]

                desktop_file_path = APP_INSTALL_DESKTOP_PATH + self.pkgname + '.desktop'
                if os.path.exists(desktop_file_path):
                    desktop_file = open(desktop_file_path, 'r')
                    for line in desktop_file.readlines():
                        if line[:5] == "Name=": 
                            #FIXME: different languages?
                            self.title = line[5:].strip('\n')
                        if line[:5] == "Icon=":
                            self.icon = line[5:].strip('\n')
                    desktop_file.close()

                # check arch
                arch = deb._sections["Architecture"]
                if  arch != "all" and arch != get_current_arch():
                    self.error = _("The file \"%s\" can not be installed on this type of computer.") %  request.split('/')[-1]

                # check conflicts and check if installing it would break anything on the current system
                if not deb.check_conflicts() or not deb.check_breaks_existing_packages():
                    # this also occurs when a package provides and conflicts, so message is not accurate..
                    self.error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % request.split('/')[-1]

                # try to satisfy the dependencies
                if not deb._satisfy_depends(deb.depends):
                    self.error = _("The file \"%s\" requires other software packages to be installed that are not available, so can not be installed.") % request.split('/')[-1]

                # check for conflicts again (this time with the packages that are marked for install)
                if not deb.check_conflicts():
                    self.error = _("The file \"%s\" conflicts with packages installed on your computer, so can not be installed.") % request.split('/')[-1]

                # get warnings
                # FIXME: we need nicer messages here..
                version_status = deb.compare_to_version_in_cache()
                if version_status == DEB_NOT_IN_CACHE:
                    # we allow users to install the deb file
                    self.status = PKG_STATE_UNINSTALLED
                    self.warning = _("Only install deb files if you trust both the author and the distributor.")
                if version_status == DEB_OLDER_THAN_CACHE:
                    if not cache[self.pkgname].installed:
                        # we allow users to install the deb file
                        self.status = PKG_STATE_UNINSTALLED
                        self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
                    else:
                        self.status = PKG_STATE_INSTALLED
                if version_status == DEB_EQUAL_TO_CACHE:
                    # we allow users to install the deb file (reinstall)
                    self.status = PKG_STATE_REINSTALLABLE
                    self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
                if version_status == DEB_NEWER_THAN_CACHE:
                    if cache[self.pkgname].installed:
                        self.status = PKG_STATE_UPGRADABLE
                    else:
                        self.status = PKG_STATE_UNINSTALLED
                    # we allow users to install the deb file (install/upgrade)
                    self.warning = _("An older version of \"%s\" is available in your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title

                # find related package in the archives
                #if (self.app.pkgname in self.cache and self.cache[self.app.pkgname].candidate):
                #    self.pkg = self.cache[self.app.pkgname]
                return
        #not deb-file
        # init app specific data
        self.app = app

        # other data
        #self.homepage_url = None
        self.channelfile = None
        self.channelname = None
        #self.doc = None

        # get xapian document
        try:
            # get xapian document
            self.doc = self.db.get_xapian_document(self.app.appname, self.pkgname)
        except IndexError:
            self.error = _("There isn't a software package called \"%s\" in your current software sources.") % self.pkgname.capitalize()
            self.icon = MISSING_PKG_ICON
            self.title = _("Not Found")
            return

        self.price = self.distro.get_price(self.doc)
        self.subtitle = self.db.get_summary(self.doc)



        # get icon
        iconname = self.db.get_iconname(self.doc)
        # remove extension (e.g. .png) because the gtk.IconTheme
        # will find fins a icon with it
        iconname = os.path.splitext(iconname)[0]
        self.icon = iconname

        # get apt cache data
        self.pkgname = self.db.get_pkgname(self.doc)
        self.pkg = None
        if (self.pkgname in cache and
            cache[self.pkgname].candidate):
            self.pkg = cache[self.pkgname]
        if self.pkg:
            self.homepage_url = self.pkg.candidate.homepage
            if self.pkg.candidate:
                self.version = self.pkg.candidate.version

        # get the component (main, universe, ..) for the given pkg object
        # this uses the data from apt, if there is none it uses the 
        # data from the app-install-data files
        if not self.pkg or not self.pkg.candidate:
            self.component = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        else:
            for origin in self.pkg.candidate.origins:
                if (origin.origin == "Ubuntu" and 
                    origin.trusted and 
                    origin.component):
                    self.component =  origin.component

        self.maintainance_time = self.distro.get_maintenance_status(cache, self.title or self.pkgname, self.pkgname, self.component, self.channelfile)
        self.license = self.distro.get_license_text(self.component).split()[1]

        # if we do not have a package in our apt data explain why
        # FIXME: This needs a quick test
        if not self.pkg:
            available_for_arch = self._available_for_our_arch()
            if not available_for_arch and (self.channelname or self.component):
                # if we don't have a package and it has no arch/component its
                # not available for us
                self.error = _("\"%s\" is not available for this type of computer.") % self.title

        # if we do not have a package in our apt data explain why
        # FIXME: This needs a quick test
        # FIXME: Need nicer messages
        if not self.pkg and not self.error:
            if self.channelname:
                self.warning = _("\"%s\" is available from the \"%s\" source, "
                         "which you are not currently using.") % (self.app.name.capitalize(), self.channelname)
            # if we have no pkg in the apt cache, check if its available for
            # the given architecture and if it has a component associated
            if self.component:
                # FIXME: This occurs mostly when we have a desktop file for the app, but the app is not in the archives (afaik)
                # If this is the only case when this occurs, then we should change the text, else use seperate warnings
                self.warning = _("To show information about this item, "
                         "the software catalog needs updating.")



        if self.pkg:
            self.description = self.pkg.candidate.description
            # Don't handle upgrades yet
            #if pkg.installed and pkg.isUpgradable:
            #    return PKG_STATE_UPGRADABLE
            if self.pkg.installed:
                self.status = PKG_STATE_INSTALLED
            else:
                self.status = PKG_STATE_UNINSTALLED

        elif self.doc:
            channel = self.doc.get_value(XAPIAN_VALUE_ARCHIVE_CHANNEL)
            if channel:
                #path = APP_INSTALL_CHANNELS_PATH + channel +".list"
                #if os.path.exists(path):
                    #self.channelname = channel
                    #self.channelfile = path
                    ## FIXME: deal with the EULA stuff
                    #print channel
                    self.status = PKG_STATE_NEEDS_SOURCE
            # check if it comes from a non-enabled component
            elif self._unavailable_component():
                # FIXME: use a proper message here, but we are in string freeze
                self.status = PKG_STATE_UNAVAILABLE
            elif self._available_for_our_arch():
                self.status = PKG_STATE_NEEDS_SOURCE

        #return PKG_STATE_UNKNOWN

        self.installed_date = self.history.get_installed_date(self.pkgname)

        self.screenshot_small = self.distro.SCREENSHOT_THUMB_URL % self.pkgname
        self.screenshot_large = self.distro.SCREENSHOT_LARGE_URL % self.pkgname

    def _unavailable_component(self):
        """ 
        check if the given doc refers to a component (like universe)
        that is currently not enabled
        """
        # FIXME: use self.component here instead?
        component =  self.doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
        logging.debug("component: '%s'" % component)
        # if there is no component accociated, it can not be unavailable
        if not component:
            return False
        distro_codename = self.distro.get_codename()
        available = self.cache.component_available(distro_codename, component)
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

    #FIXME: pgg - unneeded afaics

    def get_iconname(self):
        if self.app_details.icon:
            if self.icons.has_icon(iconname):
                return self.app_details.icon
        return 'gnome-other'

    def get_installed(self):
        if self.pkg and self.pkg.installed:
            return True
        return False

    #FIXME: pgg

