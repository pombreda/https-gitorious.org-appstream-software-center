#!/usr/bin/python

import os
import sys
import xapian

sys.path.insert(0, "../")
from softwarecenter.enums import *
from softwarecenter.utils import *

def parse_query(parser, search_string):
    str_to_prefix = { 'section' : 'AE',
                      'type' : 'AT',
                      'category' : 'AC' 
                    }
    for st in search_string.split():
        (search_prefix, search_term) = st.split(":")
        if search_prefix == "section":
            t = str_to_prefix[search_prefix]
            s = search_term.lower()
            query = xapian.Query(t+s)
            for pre in ["universe","multiverse","restricted"]:
                query = xapian.Query(xapian.Query.OP_OR,
                                     query,
                                     xapian.Query("%s%s/%s" % (t,pre,s)))
                query = xapian.Query(xapian.Query.OP_OR,
                                     query,
                                     xapian.Query("XS%s/%s" % (pre,s)))
                
        else:
            query = xapian.Query(str_to_prefix[search_prefix]+search_term.lower())  
        enquire = xapian.Enquire(db)
        enquire.set_query(query)
        with ExecutionTime("Search took"):
            mset = enquire.get_mset(0, db.get_doccount())
            print "Found %i documents for search '%s'\n" % (len(mset), st)
            for m in mset:
                doc = m[xapian.MSET_DOCUMENT]
                appname = doc.get_data()
                pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
                print "%s ; %s" % (appname, pkgname)

if __name__ == "__main__":

    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)

    axi = xapian.Database("/var/lib/apt-xapian-index/index")
    db.add_database(axi)
    parser = xapian.QueryParser()
    parser.set_database(db)
    
    if len(sys.argv) < 2:
        print "example usage: "
        print " section:net"
        print " category:AudioVideo"
        print " type:Application"
        sys.exit(1)

    parse_query(parser, sys.argv[1])
