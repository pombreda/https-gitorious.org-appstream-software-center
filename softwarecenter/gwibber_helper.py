# check gwibber has any accounts setup

import json
#from dbus.mainloop.glib import DBusGMainLoop
try:
    from gwibber.lib import GwibberPublic
    _gwibber_is_available = True
    #DBusGMainLoop(set_as_default=True)
    Gwibber = GwibberPublic()
except:
    _gwibber_is_available = False


def gwibber_is_available():
    return _gwibber_is_available

def gwibber_has_accounts():
    if not _gwibber_is_available:
        return False
    return len(json.loads(Gwibber.GetAccounts())) > 0


GWIBBER_SERVICE_AVAILABLE = gwibber_is_available() and gwibber_has_accounts()




