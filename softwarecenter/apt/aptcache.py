# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# Parts taken from gnome-app-install:utils.py (also written by Michael Vogt)
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
import datetime
import locale
import glib
import gobject
import gtk
import os
import subprocess
import time

from gettext import gettext as _

class GtkMainIterationProgress(apt.progress.OpProgress):
    """Progress that just runs the main loop"""
    def update(self, percent):
        while gtk.events_pending():
            gtk.main_iteration()

# FIXME: this stuff should move into a seperate per-distro backend
def get_maintenance_end_date(release_date, m_months):
    """
    get the (year, month) tuple when the maintenance for the distribution
    ends
    """
    years = m_months / 12
    months = m_months % 12
    support_end_year = release_date.year + years + (release_date.month + months)/12
    support_end_month = (release_date.month + months) % 12
    return (support_end_year, support_end_month)

def get_release_date_from_release_file(path):
    """
    return the release date as time_t for the given release file
    """
    if not path or not os.path.exists(path):
        return None
    tag = apt_pkg.ParseTagFile(open(path))
    tag.Step()
    if not tag.Section.has_key("Date"):
        return None
    date = tag.Section["Date"]
    return apt_pkg.StrToTime(date)

def get_release_filename_for_pkg(cache, pkgname, label, release):
    " get the release file that provides this pkg "
    if not cache.has_key(pkgname):
        return None
    pkg = cache[pkgname]
    ver = None
    # look for the version that comes from the repos with
    # the given label and origin
    for aver in pkg._pkg.VersionList:
        if aver == None or aver.FileList == None:
            continue
        for verFile, index in aver.FileList:
            #print verFile
            if (verFile.Origin == label and
                verFile.Label == label and
                verFile.Archive == release):
                ver = aver
    if not ver:
        return None
    indexfile = cache._list.FindIndex(ver.FileList[0][0])
    for metaindex in cache._list.List:
        for m in metaindex.IndexFiles:
            if (indexfile and
                indexfile.Describe == m.Describe and
                indexfile.IsTrusted):
                dir = apt_pkg.Config.FindDir("Dir::State::lists")
                name = apt_pkg.URItoFileName(metaindex.URI)+"dists_%s_Release" % metaindex.Dist
                return dir+name
    return None


class AptCache(gobject.GObject):
    """ 
    A apt cache that opens in the background and keeps the UI alive
    """

    __gsignals__ = {'cache-ready':  (gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    'cache-invalid':(gobject.SIGNAL_RUN_FIRST,
                                     gobject.TYPE_NONE,
                                     ()),
                    }

    def __init__(self):
        gobject.GObject.__init__(self)
        self._cache = None
        self._ready = False
        glib.timeout_add(100, self.open)
    def open(self):
        self._ready = False
        self.emit("cache-invalid")
        if self._cache == None:
            self._cache = apt.Cache(GtkMainIterationProgress())
        else:
            self._cache.open(GtkMainIterationProgress())
        self._ready = True
        self.emit("cache-ready")
    def __getitem__(self, key):
        return self._cache[key]
    def __iter__(self):
        return self._cache.__iter__()
    def __contains__(self, k):
        return self.cache.__contains__(k)
    def has_key(self, key):
        return self._cache.has_key(key)
    @property
    def ready(self):
        return self._ready

    # FIXME: sucks here
    def get_distro_codename(self):
       if not hasattr(self ,"codename"):
            self.codename = subprocess.Popen(
                ["lsb_release","-c","-s"],
                stdout=subprocess.PIPE).communicate()[0].strip()
       return self.codename

    def get_maintenance_status(self, appname, pkgname, component, channel):

        # try to figure out the support dates of the release and make
        # sure to look only for stuff in "Ubuntu" and "distro_codename"
        # (to exclude stuff in ubuntu-updates for the support time 
        # calculation because the "Release" file time for that gets
        # updated regularly)
        releasef = get_release_filename_for_pkg(self._cache, pkgname, 
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
    c = AptCache()
    c.open()
    print c.get_maintenance_status("synaptic app", "synaptic", "main", None)
    print c.get_maintenance_status("3dchess app", "3dchess", "universe", None)
