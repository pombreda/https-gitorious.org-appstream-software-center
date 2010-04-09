# Copyright (C) 2009 Canonical
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

import apt
import apt_pkg
import logging
import time
import xml.sax.saxutils

# define additional entities for the unescape method, needed
# because only '&amp;', '&lt;', and '&gt;' are included by default
ESCAPE_ENTITIES = {"&apos;":"'",
                   '&quot;':'"'}

class ExecutionTime(object):
    """
    Helper that can be used in with statements to have a simple
    measure of the timming of a particular block of code, e.g.
    with ExecutinTime("db flush"):
        db.flush()
    """
    def __init__(self, info=""):
        self.info = info
    def __enter__(self):
        self.now = time.time()
    def __exit__(self, type, value, stack):
        print "%s: %s" % (self.info, time.time() - self.now)

def get_http_proxy_string_from_gconf():
    """Helper that gets the http proxy from gconf

    Returns: string with http://auth:pw@proxy:port/ or None
    """
    try:
        import gconf, glib
        client = gconf.client_get_default()
        if client.get_bool("/system/http_proxy/use_http_proxy"):
            authentication = ""
            if client.get_bool("/system/http_proxy/use_authentication"):
                user = client.get_string("/system/http_proxy/authentication_user")
                password = client.get_string("/system/http_proxy/authentication_password")
                authentication = "%s:%s@" % (user, password)
            host = client.get_string("/system/http_proxy/host")
            port = client.get_int("/system/http_proxy/port")
            http_proxy = "http://%s%s:%s/" %  (authentication, host, port)
            return http_proxy
    except Exception:
        logging.exception("failed to get proxy from gconf")
    return None

def encode_for_xml(unicode_data, encoding="ascii"):
    """ encode a given string for xml """
    return unicode_data.encode(encoding, 'xmlcharrefreplace')

def decode_xml_char_reference(s):
    """ takes a string like 
        'Search&#x2026;' 
        and converts it to
        'Search...'
    """
    import re
    p = re.compile("\&\#x(\d\d\d\d);")
    return p.sub(r"\u\1", s).decode("unicode-escape")
    
def unescape(text):
    """
    unescapes the given text
    """
    return xml.sax.saxutils.unescape(text, ESCAPE_ENTITIES)

def get_current_arch():
    return apt_pkg.Config.Find("Apt::Architecture")

if __name__ == "__main__":
    s = decode_xml_char_reference('Search&#x2026;')
    print s
    print type(s)
    print unicode(s)
