#!/usr/bin/python

import glib
import logging
import time

from aptdaemon.client import AptClient

MAX_ACTIVE=1
active = 0

def exit_handler(trans, enum):
    global active
    active -= 1
    return True

if __name__ == "__main__":
    debconf_log = logging.getLogger("AptClient.DebconfProxy")
    logging.basicConfig(level=logging.DEBUG)
    print debconf_log
    debconf_log.setLevel(logging.DEBUG)

    context = glib.main_context_default()
    c = AptClient()
    for i in range(100):
        logging.debug("loop: nr: %s active: %s" % (i, active))
        
        t = c.install_packages(["3dchess"], exit_handler=exit_handler)
        t.run(block=False)
        active += 1
        t = c.install_packages(["2vcard"], exit_handler=exit_handler)
        t.run(block=False)
        active += 1
        
        t = c.remove_packages(["3dchess","2vcard"], exit_handler=exit_handler)
        t.run(block=False)
        active += 1

        while active > MAX_ACTIVE:
            while context.pending():
                context.iteration()
            time.sleep(1)
