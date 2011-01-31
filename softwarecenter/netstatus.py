import dbus
import gobject

from dbus.mainloop.glib import DBusGMainLoop

dbus_loop = DBusGMainLoop()
bus = dbus.SystemBus(mainloop=dbus_loop)

nm = bus.get_object('org.freedesktop.NetworkManager',
                    '/org/freedesktop/NetworkManager')

NETWORK_STATE = nm.state(dbus_interface='org.freedesktop.NetworkManager')

def __connection_state_changed_handler(state):
    global NETWORK_STATE

    NETWORK_STATE = int(state)
    __WATCHER__.emit("changed", NETWORK_STATE)
    return

bus.add_signal_receiver(__connection_state_changed_handler,
                        dbus_interface="org.freedesktop.NetworkManager",
                        signal_name="StateChanged")


# enums
class NetState:
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


# simple watcher which notifys subscribers to network events...
class NetworkStatusWatcher(gobject.GObject):

    __gsignals__ = {'changed':(gobject.SIGNAL_RUN_FIRST,
                               gobject.TYPE_NONE,
                               (int,)),
                   }

    def __init__(self):
        gobject.GObject.__init__(self)
        return


def get_network_state():
    return NETWORK_STATE

# global watcher
__WATCHER__ = NetworkStatusWatcher()
def get_network_watcher():
    return __WATCHER__


if __name__ == '__main__':
    loop = gobject.MainLoop()
    loop.run()

