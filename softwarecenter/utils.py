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
    
if __name__ == "__main__":
    s = decode_xml_char_reference('Search&#x2026;')
    print s
    print type(s)
    print unicode(s)
