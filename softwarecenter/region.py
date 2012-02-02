# Copyright (C) 2012 Canonical
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

import locale

def get_region():
    """ return estimate about the current region """
    # FIXME: this should use some geolocation service 
    # use LC_MONETARY as the best guess
    try:
        loc = locale.getlocale(locale.LC_MONETARY)[0]
    except Exception as e:
        LOG.warn("Failed to get locale: '%s'" % e)
        return ""
    if not loc:
        return ""
    return loc.split("_")[1]


def get_region_geoclue():
    """ return the region from a geoclue provider """
    return {}
