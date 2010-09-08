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


import subprocess
import logging

from gettext import gettext as _

class UnimplementedError(Exception):
    pass

class Distro(object):
    """ abstract base class for a distribution """
    
    # missing thumbnail
    IMAGE_THUMBNAIL_MISSING = "/usr/share/software-center/images/dummy-thumbnail-ubuntu.png"
    IMAGE_FULL_MISSING = "/usr/share/software-center/images/dummy-screenshot-ubuntu.png"

    def get_app_name(self):
        """ 
        The name of the application (as displayed in the main window and 
        the about window)
        """
        return _("Software Center")

    def get_app_description(self):
        """ 
        The description of the application displayed in the about dialog
        """
        return _("Lets you choose from thousands of free applications available for your system.")


    def get_distro_channel_name(self):
        """ The name of the main channel in the Release file (e.g. Ubuntu)"""
        return "none"
 
    def get_distro_channel_description(self):
        """ The description for the main distro channel """
        return "none"

    def get_codename(self):
        """ The codename of the distro, e.g. lucid """
        if not hasattr(self, "_distro_code_name"):
            self._distro_code_name = subprocess.Popen(
                ["lsb_release","-c","-s"], 
                stdout=subprocess.PIPE).communicate()[0].strip()
        return self._distro_code_name

    def get_installation_status(self, pkg):
        raise UnimplementedError

    def get_maintenance_status(self, cache, appname, pkgname, component, channelname):
        raise UnimplementedError

    def get_license_text(self, component):
        raise UnimplementedError

    def is_supported(self, cache, doc, pkgname):
        """ 
        return True if the given document and pkgname is supported by 
        the distribution
        """
        raise UnimplementError

    def get_supported_query(self):
        """ return a xapian query that gives all supported documents """
        import xapian
        return xapian.Query()

    def get_install_warning_text(self, cache, pkg, appname, depends):
        primary = _("To install %s, these items must be removed:" % appname)
        button_text = _("Install Anyway")

        # alter it if a meta-package is affected
        for m in depends:
            if cache[m].section == "metapackages":
                primary = _("If you install %s, future updates will not "
                              "include new items in <b>%s</b> set. "
                              "Are you sure you want to continue?") % (appname, cache[m].installed.summary)
                button_text = _("Install Anyway")
                depends = []
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in depends:
                primary = _("Installing %s may cause core applications to "
                            "be removed. "
                            "Are you sure you want to continue?" % appname)
                button_text = _("Install Anyway")
                depends = None
                break
        return (primary, button_text)

def _get_distro():
    distro_id = subprocess.Popen(["lsb_release","-i","-s"], 
                                 stdout=subprocess.PIPE).communicate()[0].strip()
    logging.getLogger("softwarecenter.distro").debug("get_distro: '%s'" % distro_id)
    # start with a import, this gives us only a softwarecenter module
    module =  __import__(distro_id, globals(), locals(), [], -1)
    # get the right class and instanciate it
    distro_class = getattr(module, distro_id)
    instance = distro_class()
    return instance

def get_distro():
    """ factory to return the right Distro object """
    return distro_instance

# singelton
distro_instance=_get_distro()


if __name__ == "__main__":
    print get_distro()
