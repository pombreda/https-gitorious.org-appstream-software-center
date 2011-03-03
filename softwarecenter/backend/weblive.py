#!/usr/bin/python

import getpass
import glib
import os
import pprint
import random
import socket
import subprocess
import sys

from threading import Thread, Event
from weblive_pristine import WebLive

class ServerNotReadyError(Exception):
    pass

class WebLiveBackend(object):
    """ backend for interacting with the weblive service """

    # NXML template
    NXML_TEMPLATE = """
<!DOCTYPE NXClientLibSettings>
<NXClientLibSettings>
<option key="Connection Name" value="WL_NAME"></option>
<option key="Server Hostname" value="WL_SERVER"></option>
<option key="Server Port" value="WL_PORT"></option>
<option key="Session Type" value="unix-application"></option>
<option key="Custom Session Command" value="WL_COMMAND"></option>
<option key="Disk Cache" value="64"></option>
<option key="Image Cache" value="16"></option>
<option key="Link Type" value="adsl"></option>
<option key="Use Render Extension" value="True"></option>
<option key="Image Compression Method" value="JPEG"></option>
<option key="JPEG Compression Level" value="9"></option>
<option key="Desktop Geometry" value=""></option>
<option key="Keyboard Layout" value="defkeymap"></option>
<option key="Keyboard Type" value="pc102/defkeymap"></option>
<option key="Media" value="False"></option>
<option key="Agent Server" value=""></option>
<option key="Agent User" value=""></option>
<option key="CUPS Port" value="0"></option>
<option key="Authentication Key" value=""></option>
<option key="Use SSL Tunnelling" value="True"></option>
<option key="Enable Fullscreen Desktop" value="False"></option>
</NXClientLibSettings>
"""
    URL = os.environ.get('SOFTWARE_CENTER_WEBLIVE_HOST',
        'https://weblive.stgraber.org/weblive/json')
    QTNX = "/usr/bin/qtnx"
    DEFAULT_SERVER = "ubuntu-natty01"

    def __init__(self):
        self.weblive = WebLive(self.URL,True)
        self.available_servers = []
        self._ready = Event()

    @property
    def ready(self):
        """ return true if data from the remote server was loaded
        """
        return self._ready.is_set()

    @classmethod
    def is_supported(cls):
        """ return if the current system will work (has the required
            dependencies
        """
        # FIXME: also test if package is available on the weblive server
        if (os.path.exists(cls.QTNX) and
            "SOFTWARE_CENTER_ENABLE_WEBLIVE" in os.environ):
            return True
        return False

    def query_available(self):
        """ (sync) get available server and limits """
        servers=self.weblive.list_everything()
        return servers

    def query_available_async(self):
        """ query available in a thread and set self.ready """
        def _query_available_helper():
            self.available_servers = self.query_available()
            self._ready.set()

        self._ready.clear()
        p = Thread(target=_query_available_helper)
        p.start()

    def is_pkgname_available_on_server(self, pkgname, serverid=None):
        for server in self.available_servers:
            if not serverid or server.name == serverid:
                for pkg in server.packages:
                    if pkg.pkgname == pkgname:
                        return True
        return False

    def get_servers_for_pkgname(self, pkgname):
        servers=[]
        for server in self.available_servers:
            # No point in returning a server that's full
            if server.current_users >= server.userlimit:
                continue

            for pkg in server.packages:
                if pkg.pkgname == pkgname:
                    servers.append(server)
        return servers

    def create_automatic_user_and_run_session(self, serverid=None,
                                              session="desktop", wait=False):
        """ login into serverid and automatically create a user """
        if not serverid:
            serverid = self.DEFAULT_SERVER

        hostname = socket.gethostname()
        username = "%s%s" % (os.environ['USER'], hostname)
        password = hostname

        connection=self.weblive.create_user(serverid, username, "WebLive User", password, session)
        self._spawn_qtnx(connection[0], connection[1], session, username, password, wait)

    def _spawn_qtnx(self, host, port, session, username, password, wait):
        if not os.path.exists(self.QTNX):
            raise IOError("qtnx not found")
        if not os.path.exists(os.path.expanduser('~/.qtnx')):
            os.mkdir(os.path.expanduser('~/.qtnx'))
        filename=os.path.expanduser('~/.qtnx/%s-%s-%s.nxml') % (
            host, port, session)
        nxml=open(filename,"w+")
        config=self.NXML_TEMPLATE
        config=config.replace("WL_NAME","%s-%s-%s" % (host, port, session))
        config=config.replace("WL_SERVER", socket.gethostbyname(host))
        config=config.replace("WL_PORT",str(port))
        config=config.replace("WL_COMMAND","vmmanager-session %s" % session)
        nxml.write(config)
        nxml.close()

        cmd = [self.QTNX,
               '%s-%s-%s' % (str(host), str(port), str(session)),
               username,
               password]

        if wait == False:
            (pid, stdin, stdout, stderr) = glib.spawn_async(
                cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD)
            glib.child_watch_add(pid, self._on_qtnx_exit)
        else:
            p=subprocess.Popen(cmd)
            p.wait()

    def _on_qtnx_exit(self, pid, status):
        print "_on_qtnx_exit ", os.WEXITSTATUS(status)

# singleton
_weblive_backend = None
def get_weblive_backend():
    global _weblive_backend
    if _weblive_backend is None:
        _weblive_backend = WebLiveBackend()
        # initial query
        if _weblive_backend.is_supported():
            _weblive_backend.query_available_async()
    return _weblive_backend

if __name__ == "__main__":
    weblive = get_weblive_backend()
    weblive.query_available_async()
    weblive._ready.wait()

    print weblive.available_servers

    # run session
    weblive.create_automatic_user_and_run_session(session="firefox",wait=True)
