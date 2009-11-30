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

from aptutils import *
from softwarecenter.distro import Distro
from gettext import gettext as _

class Debian(Distro):

    # metapackages
    IMPORTANT_METAPACKAGES = ("kde", "gnome", "gnome-desktop-environment")

    # screenshot handling
    SCREENSHOT_THUMB_URL =  "http://screenshots.debian.net/thumbnail/%s"
    SCREENSHOT_LARGE_URL = "http://screenshots.debian.net/screenshot/%s"

    def get_removal_warning_text(self, cache, pkg, appname):
        primary = _("To remove %s, these items must be removed "
                    "as well:" % appname)
        button_text = _("Remove All")

        depends = list(cache.get_installed_rdepends(pkg))

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

    def get_rdepends_text(self, cache, pkg, appname):
        s = ""
        if pkg.installed:
            # generic message
            s = _("%s is installed on this computer.") % appname
            # show how many packages on the system depend on this
            installed_rdeps = cache.get_installed_rdepends(pkg)
            installed_rrecommends = cache.get_installed_rrecommends(pkg)
            installed_rsuggests = cache.get_installed_rsuggests(pkg)
            if len(installed_rdeps) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is used by %s piece of installed software.",
                    "It is used by %s pieces of installed software.",
                    len(installed_rdeps)) % len(installed_rdeps)
            elif len(installed_rrecommends) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is recommended by %s piece of installed software.",
                    "It is recommended by %s pieces of installed software.",
                    len(installed_rrecommends)) % len(installed_rrecommends)
            elif len(installed_rsuggests) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is suggested by %s piece of installed software.",
                    "It is suggested by %s pieces of installed software.",
                    len(installed_rrecommends)) % len(installed_rrecommends)
        return s

    def get_distro_codename(self):
       if not hasattr(self ,"codename"):
            self.codename = subprocess.Popen(
                ["lsb_release","-c","-s"],
                stdout=subprocess.PIPE).communicate()[0].strip()
       return self.codename

    def get_license_text(self, component):
        li =  _("Unknown")
        if component in ("main",):
            li = _("Open Source")
        elif component == "contrib":
            li = _("Open Source with proprietary parts")
        elif component == "restricted":
            li = _("Proprietary")
        s = _("License: %s") % li
        return s

    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        return ""


if __name__ == "__main__":
    import apt
    cache = apt.Cache()
    print c.get_maintenance_status(cache, "synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status(cache, "3dchess app", "3dchess", "universe", None)
