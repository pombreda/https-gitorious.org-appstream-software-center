# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Julian Andres Klode
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

import datetime
import gettext
import locale
import subprocess

from apt.utils import *
from softwarecenter.distro import Distro
from gettext import gettext as _

class Debian(Distro):

    # metapackages
    IMPORTANT_METAPACKAGES = ("kde", "gnome", "gnome-desktop-environment")

    # screenshot handling
    SCREENSHOT_THUMB_URL =  "http://screenshots.debian.net/thumbnail/%(pkgname)s"
    SCREENSHOT_LARGE_URL = "http://screenshots.debian.net/screenshot/%(pkgname)s"

    def get_distro_channel_name(self):
        """ The name in the Release file """
        return "Debian"

    def get_distro_channel_description(self):
        """ The description of the main distro channel """
        return _("Provided by Debian")

    def get_removal_warning_text(self, cache, pkg, appname, depends):
        primary = _("To remove %s, these items must be removed "
                    "as well:") % appname
        button_text = _("Remove All")

        # alter it if a meta-package is affected
        for m in depends:
            if cache[m].section == "metapackages":
                primary = _("If you uninstall %s, future updates will not "
                              "include new items in <b>%s</b> set. "
                              "Are you sure you want to continue?") % (appname, cache[m].installed.summary)
                button_text = _("Remove Anyway")
                depends = []
                break

        # alter it if an important meta-package is affected
        for m in self.IMPORTANT_METAPACKAGES:
            if m in depends:
                primary = _("%s is a core application in Debian. "
                              "Uninstalling it may cause future upgrades "
                              "to be incomplete. Are you sure you want to "
                              "continue?") % appname
                button_text = _("Remove Anyway")
                depends = None
                break
        return (primary, button_text)
        
    def get_deauthorize_text(self, account_name, purchased_packages):
        if len(purchased_packages) == 0:
            if account_name:
                primary = _('Are you sure you want to deauthorize this computer '
                            'from the "%s" account?') % account_name
            else:
                primary = _('Are you sure you want to deauthorize this computer '
                            'for purchases?')
            button_text = _('Deauthorize')
        else:
            if account_name:
                primary = _('Deauthorizing this computer from the "%s" account '
                            'will remove this purchased software:') % account_name
            else:
                primary = _('Deauthorizing this computer for purchases '
                            'will remove the following purchased software:')
            button_text = _('Remove All')
        return (primary, button_text)

    def get_distro_codename(self):
        if not hasattr(self ,"codename"):
            self.codename = subprocess.Popen(
                ["lsb_release","-c","-s"],
                stdout=subprocess.PIPE).communicate()[0].strip()
        return self.codename

    def get_license_text(self, component):
        if component in ("main",):
            return _("Open source")
        elif component == "contrib":
            return _("Open source, with proprietary parts")
        elif component == "restricted":
            return _("Proprietary")

    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        return ""


if __name__ == "__main__":
    import apt
    cache = apt.Cache()
    print c.get_maintenance_status(cache, "synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status(cache, "3dchess app", "3dchess", "universe", None)
