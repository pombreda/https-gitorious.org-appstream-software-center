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

# Start of copy from weblive.py in upstream branch
import urllib, urllib2, json

class WebLiveJsonError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class WebLiveError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class WebLiveLocale(object):
    def __init__(self, locale, description):
        self.locale = locale
        self.description = description

class WebLivePackage(object):
    def __init__(self, pkgname, version):
        self.pkgname = pkgname
        self.version = version

class WebLiveServer(object):
    def __init__(self, name, title, description, timelimit, userlimit, users):
        self.name = name
        self.title = title
        self.description = description
        self.timelimit = timelimit
        self.userlimit = userlimit
        self.current_users = users

    def __repr__(self):
        return "[WebLiveServer: %s (%s - %s), timelimit=%s, userlimit=%s, current_users=%s" % (
            self.name, self.title, self.description, self.timelimit, self.userlimit, self.current_users)

class WebLiveEverythingServer(WebLiveServer):
    def __init__(self, name, title, description, timelimit, userlimit, users, locales, packages):
        self.locales = [WebLiveLocale(x[0], x[1]) for x in locales]
        self.packages = [WebLivePackage(x[0], x[1]) for x in packages]

        WebLiveServer.__init__(self, name, title, description, timelimit, userlimit, users)

    def __repr__(self):
        return "[WebLiveServer: %s (%s - %s), timelimit=%s, userlimit=%s, current_users=%s, nr_locales=%s, nr_pkgs=%s" % (
            self.name, self.title, self.description, self.timelimit, self.userlimit, self.current_users, len(self.locales), len(self.packages))

class WebLive:
    def __init__(self,url,as_object=False):
        self.url=url
        self.as_object=as_object

    def do_query(self,query):
        page=urllib2.Request(self.url,urllib.urlencode({'query':json.dumps(query)}))

        try:
            response=urllib2.urlopen(page)
        except urllib2.HTTPError, e:
            raise WebLiveJsonError("HTTP return code: %s" % e.code)
        except urllib2.URLError, e:
            raise WebLiveJsonError("Failed to reach server: %s" % e.reason)

        try:
            reply=json.loads(response.read())
        except ValueError:
            raise WebLiveJsonError("Returned json object is invalid.")

        if reply['status'] != 'ok':
            if reply['message'] == -1:
                raise WebliveJsonError("Missing 'action' field in query.")
            elif reply['message'] == -2:
                raise WebLiveJsonError("Missing parameter")
            elif reply['message'] == -3:
                raise WebliveJsonError("Function '%s' isn't exported over JSON." % query['action'])
            else:
                raise WebLiveJsonError("Unknown error code: %s" % reply['message'])

        if 'message' not in reply:
            raise WebLiveJsonError("Invalid json reply")

        return reply

    def create_user(self,serverid,username,fullname,password,session="desktop"):
        query={}
        query['action']='create_user'
        query['serverid']=serverid
        query['username']=username
        query['fullname']=fullname
        query['password']=password
        query['session']=session
        reply=self.do_query(query)

        if type(reply['message']) != type([]):
            if reply['message'] == 1:
                raise WebLiveError("Reached user limit, return false.")
            elif reply['message'] == 2:
                raise WebLiveError("Different user with same username already exists.")
            elif reply['message'] == 3:
                raise WebLiveError("Invalid fullname, must only contain alphanumeric characters and spaces.")
            elif reply['message'] == 4:
                raise WebLiveError("Invalid login, must only contain lowercase letters.")
            elif reply['message'] == 5:
                raise WebLiveError("Invalid password, must contain only alphanumeric characters.")
            elif reply['message'] == 7:
                raise WebLiveError("Invalid server: %s" % serverid)
            else:
                raise WebLiveError("Unknown error code: %s" % reply['message'])

        return reply['message']

    def list_everything(self):
        query={}
        query['action']='list_everything'
        reply=self.do_query(query)

        if type(reply['message']) != type({}):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}),type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            servers=[]
            for server in reply['message']:
                attr=reply['message'][server]
                servers.append(WebLiveEverythingServer(
                    server,
                    attr['title'],
                    attr['description'],
                    attr['timelimit'],
                    attr['userlimit'],
                    attr['users'],
                    attr['locales'],
                    attr['packages']))
            return servers

    def list_locales(self,serverid):
        query={}
        query['action']='list_locales'
        query['serverid']=serverid
        reply=self.do_query(query)

        if type(reply['message']) != type([]):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}),type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            return [WebLiveLocale(x[0], x[1]) for x in reply['message']]

    def list_packages(self,serverid):
        query={}
        query['action']='list_packages'
        query['serverid']=serverid
        reply=self.do_query(query)

        if type(reply['message']) != type([]):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}),type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            return [WebLivePackage(x[0], x[1]) for x in reply['message']]

    def list_servers(self):
        query={}
        query['action']='list_servers'
        reply=self.do_query(query)

        if type(reply['message']) != type({}):
            raise WebLiveError("Invalid value, expected '%s' and got '%s'."
                % (type({}),type(reply['message'])))

        if not self.as_object:
            return reply['message']
        else:
            servers=[]
            for server in reply['message']:
                attr=reply['message'][server]
                servers.append(WebLiveServer(
                    server,
                    attr['title'],
                    attr['description'],
                    attr['timelimit'],
                    attr['userlimit'],
                    attr['users']))
            return servers
# End of copy from weblive.py in upstream branch

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
            for pkg in server.packages:
                if pkg.pkgname == pkgname:
                    servers.append(server.name)
        return servers

    def create_automatic_user_and_run_session(self, serverid=None,
                                              session="desktop"):
        """ login into serverid and automatically create a user """
        if not serverid:
            serverid = self.DEFAULT_SERVER

        hostname = socket.gethostname()
        username = "%s%s" % (os.environ['USER'], hostname)
        password = hostname

        connection=self.weblive.create_user(serverid, username, "WebLive User", password, session)
        self._spawn_qtnx(connection[0], connection[1], session, username, password)

    def _spawn_qtnx(self, host, port, session, username, password):
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
        #print cmd
        (pid, stdin, stdout, stderr) = glib.spawn_async(
            cmd, flags=glib.SPAWN_DO_NOT_REAP_CHILD)
        #p=subprocess.Popen(cmd)
        #p.wait()
        glib.child_watch_add(pid, self._on_qtnx_exit)

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
    weblive.ready.wait()
    print weblive.available_servers

    # run session
    weblive.create_automatic_user_and_run_session(session="firefox")
