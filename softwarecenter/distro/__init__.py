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

    def get_rdepends_text(self, pkg):
        raise UnimplementedError
    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        raise UnimplementedError

def get_distro():
    prefix = "distro"
    distro_id = subprocess.Popen(["lsb_release","-i","-s"], 
                                 stdout=subprocess.PIPE).communicate()[0].strip()
    logging.debug("get_distro: '%s'" % distro_id)
    distro_module = __import__(prefix+"."+distro_id)
    sub_distro_module = getattr(distro_module, distro_id)
    distro_class = getattr(sub_distro_module, distro_id)
    instance = distro_class()
    return instance


