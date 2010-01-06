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

import datetime
import gettext
import locale
import subprocess

from aptutils import *
from softwarecenter.distro import Distro
from gettext import gettext as _

class Ubuntu(Distro):

    # metapackages
    IMPORTANT_METAPACKAGES = ("ubuntu-desktop", "kubuntu-desktop")

    # screenshot handling
    SCREENSHOT_THUMB_URL =  "http://screenshots.ubuntu.com/thumbnail-404/%s"
    SCREENSHOT_LARGE_URL = "http://screenshots.ubuntu.com/screenshot-404/%s"

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
                primary = _("%s is a core application in Ubuntu. "
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
                    "It is used by %s installed software package.",
                    "It is used by %s installed software packages.",
                    len(installed_rdeps)) % len(installed_rdeps)
            elif len(installed_rrecommends) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is recommended by %s installed software package.",
                    "It is recommended by %s installed software packages.",
                    len(installed_rrecommends)) % len(installed_rrecommends)
            elif len(installed_rsuggests) > 0:
                s += " "
                s += gettext.ngettext(
                    "It is suggested by %s installed software package.",
                    "It is suggested by %s installed software packages.",
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
        if component in ("main", "universe"):
            li = _("Open Source")
        elif component == "restricted":
            li = _("Proprietary")
        s = _("License: %s") % li
        return s

    def get_maintenance_status(self, cache, appname, pkgname, component, channel):
        # try to figure out the support dates of the release and make
        # sure to look only for stuff in "Ubuntu" and "distro_codename"
        # (to exclude stuff in ubuntu-updates for the support time 
        # calculation because the "Release" file time for that gets
        # updated regularly)
        releasef = get_release_filename_for_pkg(cache._cache, pkgname, 
                                                "Ubuntu", 
                                                self.get_distro_codename())
        time_t = get_release_date_from_release_file(releasef)
        # check the release date and show support information
        # based on this
        if time_t:
            release_date = datetime.datetime.fromtimestamp(time_t)
            #print "release_date: ", release_date
            now = datetime.datetime.now()
            release_age = (now - release_date).days
            #print "release age: ", release_age

            # mvo: we do not define the end date very precisely
            #      currently this is why it will just display a end
            #      range
            (support_end_year, support_end_month) = get_maintenance_end_date(release_date, 18)
            support_end_month_str = locale.nl_langinfo(getattr(locale,"MON_%d" % support_end_month))
             # check if the support has ended
            support_ended = (now.year >= support_end_year and 
                             now.month > support_end_month)
            if component == "main":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates for "
                             "%(appname)s until %(support_end_month_str)s "
                             "%(support_end_year)s.") % {'appname' : appname,
                                                         'support_end_month_str' : support_end_month_str,
                                                         'support_end_year' : support_end_year}
            elif component == "restricted":
                if support_ended:
                    return _("Canonical does no longer provide "
                             "updates for %s in Ubuntu %s. "
                             "Updates may be available in a newer version of "
                             "Ubuntu.") % (appname, self.get_distro_release())
                else:
                    return _("Canonical provides critical updates supplied "
                             "by the developers of %(appname)s until "
                             "%(support_end_month_str)s "
                             "%(support_end_year)s.") % {'appname' : appname,
                                                         'support_end_month_str' : support_end_month_str,
                                                         'support_end_year' : support_end_year}
               
        # if we couldn't fiure a support date, use a generic maintenance
        # string without the date
        if channel:
            return _("Canonical does not provide updates for %s. "
                     "Some updates may be provided by the third party "
                     "vendor.") % appname
        elif component == "main":
            return _("Canonical provides critical updates for %s.") % appname
        elif component == "restricted":
            return _("Canonical provides critical updates supplied by the "
                     "developers of %s.") % appname
        elif component == "universe" or component == "multiverse":
            return _("Canonical does not provide updates for %s. "
                     "Some updates may be provided by the "
                     "Ubuntu community.") % appname
        return _("Application %s has a unkown maintenance status.") % appname


if __name__ == "__main__":
    import apt
    cache = apt.Cache()
    print c.get_maintenance_status(cache, "synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status(cache, "3dchess app", "3dchess", "universe", None)
