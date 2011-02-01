# Copyright (C) 2009 Canonical
#
# Authors:
#   Matthew McGowan
#   Michael Vogt
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

import dbus
import gobject
import logging

from dbus.mainloop.glib import DBusGMainLoop

# enums
class NetState(object):
    """ enums for network manager status """
    # The NetworkManager daemon is in an unknown state. 
    NM_STATE_UNKNOWN      = 0   
    # The NetworkManager daemon is asleep and all interfaces managed by it are inactive. 
    NM_STATE_ASLEEP       = 1
    # The NetworkManager daemon is connecting a device.
    NM_STATE_CONNECTING   = 2
    # The NetworkManager daemon is connected. 
    NM_STATE_CONNECTED    = 3
    # The NetworkManager daemon is disconnected.
    NM_STATE_DISCONNECTED = 4


class NetworkStatusWatcher(gobject.GObject):
    """ simple watcher which notifys subscribers to network events..."""
    __gsignals__ = {'changed':(gobject.SIGNAL_RUN_FIRST,
                               gobject.TYPE_NONE,
                               (int,)),
                   }

    def __init__(self):
        gobject.GObject.__init__(self)
        return

# internal helper
def __connection_state_changed_handler(state):
    global NETWORK_STATE

    NETWORK_STATE = int(state)
    __WATCHER__.emit("changed", NETWORK_STATE)
    return

# init network state
def __init_network_state():
    global NETWORK_STATE
    dbus_loop = DBusGMainLoop()
    try:
        bus = dbus.SystemBus(mainloop=dbus_loop)
        nm = bus.get_object('org.freedesktop.NetworkManager',
                            '/org/freedesktop/NetworkManager')
        NETWORK_STATE = nm.state(dbus_interface='org.freedesktop.NetworkManager')
        bus.add_signal_receiver(__connection_state_changed_handler,
                                dbus_interface="org.freedesktop.NetworkManager",
                                signal_name="StateChanged")
    except Exception as e:
        logging.warn("failed to init network state watcher '%s'" % e)
        NETWORK_STATE = NetState.NM_STATE_UNKNOWN

# global watcher
__WATCHER__ = NetworkStatusWatcher()
def get_network_watcher():
    return __WATCHER__

# simply query
def get_network_state():
    global NETWORK_STATE
    return NETWORK_STATE

# init it once
__init_network_state()

if __name__ == '__main__':
    loop = gobject.MainLoop()
    loop.run()

