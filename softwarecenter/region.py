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

from gi.repository import GObject
import dbus

from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import locale

def get_region():
    """ return dict estimate about the current countrycode/country """
    res = { 'countrycode' : '',
            'country' : '',
          }
    try:
        # use LC_MONETARY as the best guess
        loc = locale.getlocale(locale.LC_MONETARY)[0]
    except Exception as e:
        LOG.warn("Failed to get locale: '%s'" % e)
        return res
    if not loc:
        return res
    res["countrycode"] = loc.split("_")[1]
    
    return res



# the first parameter of SetRequirements
class AccuracyLevel:
 NONE = 0
 COUNTRY = 1
 REGION = 2
 LOCALITY = 3
 POSTALCODE = 4
 STREET = 5
 DETAILED = 6

class AllowedResources:
    NONE = 0
    NETWORK = 1 << 0
    CELL = 1 << 1
    GPS = 1 << 2
    ALL = (1 << 10) -1

def get_region_geoclue():
    """ return the dict with at least countrycode,country from a geoclue
        provider 
   """
    bus = dbus.SessionBus()
    master = bus.get_object(
        'org.freedesktop.Geoclue.Master', '/org/freedesktop/Geoclue/Master')
    client = bus.get_object(
        'org.freedesktop.Geoclue.Master', master.Create())
    client.SetRequirements(AccuracyLevel.COUNTRY,   # (i) accuracy_level
                           0,                       # (i) time
                           False,                   # (b) require_updates
                           AllowedResources.ALL)    # (i) allowed_resoures
    address = dbus.Interface(
        client, dbus_interface='org.freedesktop.Geoclue.Address')
    # this is crucial
    client.AddressStart()
    # now get the data
    time, address_res, accuracy = client.GetAddress()
    return address_res

