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
import subprocess

class UnimplementedError(Exception):
    pass

class Distro(object):
    """ abstract base class for a distribution """
    
    # missing thumbnail
    IMAGE_THUMBNAIL_MISSING = "/usr/share/software-center/images/dummy-thumbnail-ubuntu.png"
    IMAGE_FULL_MISSING = "/usr/share/software-center/images/dummy-screenshot-ubuntu.png"

    def get_distro_channel_name(self):
        """ The name in the Release file """
        return "none"

    def get_distro_channel_description(self):
        """ The name in the Release file """
        return "none"

    def get_rdepends_text(self, pkg):
        raise UnimplementedError

    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        raise UnimplementedError

    def get_license_text(self, component):
        raise UnimplementedError

def _get_distro():
    distro_id = subprocess.Popen(["lsb_release","-i","-s"], 
                                 stdout=subprocess.PIPE).communicate()[0].strip()
    logging.debug("get_distro: '%s'" % distro_id)
    # start with a import, this gives us only a softwarecenter module
    module =  __import__(distro_id, globals(), locals(), [], -1)
    # get the right class and instanciate it
    distro_class = getattr(module, distro_id)
    instance = distro_class()
    return instance

def get_distro():
    return distro_instance

# singelton
distro_instance=_get_distro()


if __name__ == "__main__":
    print get_distro()
