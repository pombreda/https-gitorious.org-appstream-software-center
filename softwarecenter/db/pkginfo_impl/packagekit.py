# Copyright (C) 2011 Canonical
#
# Authors:
#  Alex Eftimie
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

from gi.repository import PackageKitGlib as packagekit
import gobject
import logging

from softwarecenter.db.pkginfo import PackageInfo, _Version

class FakeOrigin:
    def __init__(self, name):
        self.origin = name
        self.trusted = True
        self.component = ''
        self.site = ''
        self.label = ''
        self.archive = ''

class PackagekitVersion(_Version):
    def __init__(self, package, pkginfo):
        self.package = package
        self.pkginfo = pkginfo

    @property
    def description(self):
        pkgid = self.package.get_id()
        return self.pkginfo.get_description(pkgid)

    @property
    def downloadable(self):
        return True #FIXME: check for an equivalent
    @property
    def summary(self):
        return self.package.get_property('summary')
    @property
    def size(self):
        return self.pkginfo.get_size(self.package.get_name())
    @property
    def installed_size(self):
        return 0 #FIXME get installed_size
    @property
    def version(self):
        return self.package.get_version()
    @property
    def origins(self):
        return self.pkginfo.get_origins(self.package.get_name())

class PackagekitInfo(PackageInfo):
    def __init__(self):
        super(PackagekitInfo, self).__init__()
        self.client = packagekit.Client()
        self._cache = {} # temporary hack for decent testing

    def __contains__(self, pkgname):
        return True # setting it like this for now

    def is_installed(self, pkgname):
        p = self._get_one_package(pkgname)
        if not p:
            return False
        return p.get_info() == packagekit.InfoEnum.INSTALLED

    def is_available(self, pkgname):
        # FIXME: i don't think this is being used
        return True

    def get_installed(self, pkgname):
        p = self._get_one_package(pkgname)
        if p.get_info() == packagekit.InfoEnum.INSTALLED:
            return PackagekitVersion(p, self) if p else None

    def get_candidate(self, pkgname):
        p = self._get_one_package(pkgname, pfilter=packagekit.FilterEnum.NEWEST)
        return PackagekitVersion(p, self) if p else None

    def get_versions(self, pkgname):
        return [PackagekitVersion(p, self) for p in self._get_packages(pkgname)]

    def get_section(self, pkgname):
        # FIXME: things are fuzzy here - group-section association
        p = self._get_one_package(pkgname)
        if p:
            return packagekit.group_enum_to_string(p.get_property('group'))

    def get_summary(self, pkgname):
        p = self._get_one_package(pkgname)
        return p.get_property('summary') if p else ''

    def get_description(self, packageid):
        p = self._get_package_details(packageid)
        return p.get_property('description') if p else ''

    def get_website(self, pkgname):
        p = self._get_one_package(pkgname)
        if not p:
            return ''
        p = self._get_package_details(p.get_id())
        return p.get_property('url') if p else ''

    def get_installed_files(self, pkgname):
        # FIXME please
        return []

    def get_size(self, pkgname):
        p = self._get_one_package(pkgname)
        if not p:
            return -1
        p = self._get_package_details(p.get_id())
        return p.get_property('size') if p else -1

    def get_installed_size(self, pkgname):
        # TODO find something
        return -1

    def get_origins(self, pkgname):
        # FIXME something
        return [FakeOrigin('unknown')]

    def get_addons(self, pkgname, ignore_installed=True):
        # FIXME
        return ([], [])

    def get_packages_removed_on_remove(self, pkg):
        """ Returns a package names list of reverse dependencies
        which will be removed if the package is removed."""
        # FIXME
        return []

    def get_packages_removed_on_install(self, pkg):
        """ Returns a package names list of dependencies
        which will be removed if the package is installed."""
        # FIXME
        return []

    def get_total_size_on_install(self, pkgname, addons_install=None,
                                addons_remove=None):
        """ Returns a tuple (download_size, installed_size)
        with disk size in KB calculated for pkgname installation
        plus addons change.
        """
        # FIXME
        return (0, 0)

    @property
    def ready(self):
        """ No PK equivalent, simply returning True """
        return True

    """ private methods """
    def _get_package_details(self, packageid, cache=True):
        if (packageid in self._cache.keys()) and cache:
            return self._cache[packageid]

        result = self.client.get_details((packageid,), None, self._on_progress_changed, None)
        pkgs = result.get_details_array()
        if not pkgs:
            return None
        self._cache[packageid] = pkgs[0]
        return pkgs[0]
            
    def _get_one_package(self, pkgname, pfilter=packagekit.FilterEnum.NONE, cache=True):
        if (pkgname in self._cache.keys()) and cache:
            return self._cache[pkgname]
        ps = self._get_packages(pkgname, pfilter)
        if not ps:
            return None
        self._cache[pkgname] = ps[0]
        return ps[0]

    def _get_packages(self, pkgname, pfilter=packagekit.FilterEnum.NONE):
        """ resolve a package name into a PkPackage object or return None """
        pfilter = 1 << pfilter
        result = self.client.resolve(pfilter,
                                     (pkgname,),
                                     None,
                                     self._on_progress_changed, None
        )
        pkgs = result.get_package_array()
        return pkgs
        
    def _on_progress_changed(self, progress, ptype, data=None):
        pass

if __name__=="__main__":
    pi = PackagekitInfo()

    print "Firefox, installed ", pi.is_installed('firefox')
