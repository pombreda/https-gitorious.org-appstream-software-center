#!/usr/bin/python

import getpass
import json
import os
import random
import socket
import subprocess
import sys
import urllib


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
    URL = 'https://www.edubuntu.org/vmmanager/json'

    def query_available(self):
        """ get available server and limits """
        query={}
        query['action']='list_everything'
        page=urllib.urlopen(self.URL,
                            urllib.urlencode({'query':json.dumps(query)}))
        servers=json.loads(page.read())
        if servers['status'] == 'ok':
            for server in servers['message']:
                attributes=servers['message'][server]
                print "== %s ==" % server
                for attribute in attributes:
                    if attribute in ('locales','packages'):
                        print " * %s: %s" % (attribute,len(attributes[attribute]))
                    else:
                        print " * %s: %s" % (attribute,attributes[attribute])
                print ""
        return []

    def create_automatic_user(self, 
                              serverid='ubuntu-natty01', 
                              session="desktop"):
        """ login into serverid and automatically create a user """
        username = os.environ['USER']
        query={}
        query['action'] = 'create_user'
        query['serverid'] = serverid
        query['username'] = username
        query['fullname'] = "WebLive User"
        query['password'] = socket.gethostname()      # bYes, the hostname is the password ;)
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

        qtnx=subprocess.Popen(['/usr/bin/qtnx',
                               '%s-%s-%s' % (host, port, session), 
                               username, 
                               password])
        ret = qtnx.wait()
        return (ret == 0)
                             
if __name__ == "__main__":
    weblive = WebLiveBackend()
    weblive.query_available()
    weblive.create_automatic_user(session="gedit")
