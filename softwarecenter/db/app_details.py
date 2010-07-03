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

class ApplicationDetails(object):
    """ This is a centralised place for all application details """
    def __init__(self, pkgname, request):
        # FIXME: do we need this? self.available = None #true if available in archive or if file exists, else false
        # self.contributors = None
        self.description = None
        # self.distributer = None
        self.error = None
        self.homepage = None
        self.icon = None
        self.license = None
        # self.maintainer = None
        # self.maintance_time = None
        self.pkgname = pkgname
        # self.supplier = None
        self.status = None #installed,in_progress,not-installed
        self.subtitle = None
        self.type = None
        self.title = None
        self.version = None
        self.warning = None

        if request:
            if request.count('/') > 0:
                # deb file


                # Constants for comparing the local package file with the version in the cache
                (DEB_NOT_IN_CACHE, DEB_OLDER_THAN_CACHE, DEB_EQUAL_TO_CACHE, DEB_NEWER_THAN_CACHE) = range(4)

                # open the package
                try:
                    deb = debfile.DebPackage(request, Cache())
                except (IOError,SystemError),e:
                    mimetype = guess_type(request)
                    if (mimetype[0] != None and mimetype[0] != "application/x-debian-package"):
                        self.error = _("The file \"%s\" is not a software package.") % request
                        self.icon = MISSING_PKG_ICON
                        self.title = _("Not Found")
                        return  
                    else:
                        self.error = _("The file \"%s\" can not be opened. Please check that the file exists and that you have permission to access it.") % request
                        self.icon = MISSING_PKG_ICON
                        self.title = _("Not Found")
                        return

                # do some stuff
                description = deb._sections["Description"]

                # set variables
                self.description = ('\n').join(description.split('\n')[1:])
                try:
                    self.homepage_url = deb._sections["Homepage"]
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
                    self.warning = _("Only install deb files if you trust both the author and the distributor.")
                if version_status == DEB_OLDER_THAN_CACHE:
                    if not self.cache[self.app.pkgname].installed:
                        # we allow users to install the deb file
                        self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
                if version_status == DEB_EQUAL_TO_CACHE:
                    # we allow users to install the deb file (reinstall)
                    self.warning = _("Please install \"%s\" via your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title
                if version_status == DEB_NEWER_THAN_CACHE:
                    # we allow users to install the deb file (install/upgrade)
                    self.warning = _("An older version of \"%s\" is available in your normal software channels. Only install deb files if you trust both the author and the distributor.") % self.title

                # find related package in the archives
                #if (self.app.pkgname in self.cache and self.cache[self.app.pkgname].candidate):
                #    self.pkg = self.cache[self.app.pkgname]
