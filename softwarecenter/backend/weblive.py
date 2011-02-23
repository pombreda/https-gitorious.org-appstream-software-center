#!/usr/bin/python

import getpass
import glib
import json
import os
import pprint
import random
import socket
import subprocess
import sys
import urllib

class ServerNotReadyError(Exception):
    pass

class WebLiveLocale(object):
    def __init__(self, locale, description):
        self.locale = locale
        self.description = description
    
class WebLivePackage(object):
    def __init__(self, pkgname, version):
        self.pkgname = pkgname
        self.version = version

class WebLiveServer(object):

    def __init__(self, name, title, description, locales, packages, timelimit, userlimit, users):
        self.name = name
        self.title = title
        self.description = description
        self.locales = [WebLiveLocale(x[0], x[1]) for x in locales]
        self.packages = [WebLivePackage(x[0], x[1]) for x in packages]
        self.timelimit = timelimit
        self.userlimit = userlimit
        self.current_users = users

    def __repr__(self):
        return "[WebLiveServer: %s (%s - %s), timelimit=%s, userlimit=%s, current_users=%s, nr_locales=%s, nr_pkgs=%s" % (
            self.name, self.title, self.description, self.timelimit, self.userlimit, self.current_users, len(self.locales), len(self.packages))

    @classmethod
    def from_json(cls, name, attributes):
        o = cls(name,
                attributes["title"],
                attributes["description"],
                attributes["locales"],
                attributes["packages"],
                attributes["timelimit"],
                attributes["userlimit"],
                attributes["users"])
        return o
        

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
    URL = 'https://weblive.stgraber.org/vmmanager/json'

    def query_available(self):
        """ (sync) get available server and limits """
        query={}
        query['action']='list_everything'
        page=urllib.urlopen(self.URL,
                            urllib.urlencode({'query':json.dumps(query)}))
        json_str = page.read()
        servers=self._server_list_from_json(json_str)
        return servers

    def _server_list_from_json(self, json_str):
        servers = []
        servers_json_dict = json.loads(json_str)
        #print pprint.pprint(servers_json_dict)
        if not servers_json_dict["status"] == "ok":
            raise ServerNotReadyError("server not ok, msg: '%s'" % \
                                          servers_json_dict["message"])

        for (servername, attributes) in servers_json_dict['message'].iteritems():
            servers.append(WebLiveServer.from_json(servername, attributes))
        return servers

    def create_automatic_user_and_run_session(self, 
                                              serverid='ubuntu-natty01', 
                                              session="desktop"):
        """ login into serverid and automatically create a user """
        hostname = socket.gethostname()
        username = "%s%s" % (os.environ['USER'], hostname)
        query={}
        query['action'] = 'create_user'
        query['serverid'] = serverid
        query['username'] = username
        query['fullname'] = "WebLive User"
        query['password'] = hostname  # FIXME: use random PW
        query['session'] = session

        # Encode and send using HTTPs
        page=urllib.urlopen(self.URL,
                            urllib.urlencode({'query':json.dumps(query)}))
        # Decode JSON reply
        result=json.loads(page.read())
        print "\nStatus: %s" % result['status']

        if result['message']:
            print "Message: %s" % result['message']
            print result
        if result['status'] == 'ok':
            host = result['message'][0]
            port = result['message'][1]
            session = query['session']
            username = query['username']
            password = query['password']
            self._spawn_qtnx(host, port, session, username, password)

    def _spawn_qtnx(self, host, port, session, username, password):
        if not os.path.exists('/usr/bin/qtnx'):
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

        cmd = ['/usr/bin/qtnx',
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
        
                             
if __name__ == "__main__":
    weblive = WebLiveBackend()
    servers = weblive.query_available()
    print servers
    weblive.create_automatic_user_and_run_session(session="firefox")
