# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#  Matthew McGowan
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


import json
#from dbus.mainloop.glib import DBusGMainLoop

#DBusGMainLoop(set_as_default=True)

try:
    from gwibber.lib import GwibberPublic
    _gwibber_is_available = True
    Gwibber = GwibberPublic()
    Gwibber.service.refresh()
except:
    _gwibber_is_available = False


def gwibber_service_available():
    if not _gwibber_is_available:
        return len(json.loads(Gwibber.GetAccounts())) > 0

GWIBBER_SERVICE_AVAILABLE = gwibber_service_available()
#print 'Gwibber Serice Available: %s' % GWIBBER_SERVICE_AVAILABLE 




