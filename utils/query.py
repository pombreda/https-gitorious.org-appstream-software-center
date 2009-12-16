#!/usr/bin/python

import os
import sys
import xapian

sys.path.insert(0, "../")
from softwarecenter.enums import *
from softwarecenter.utils import *

def run_query(parser, search_term):
    search_query = parser.parse_query(search_term, 
                                      xapian.QueryParser.FLAG_PARTIAL|
                                      xapian.QueryParser.FLAG_BOOLEAN)
    print search_query
    enquire = xapian.Enquire(db)
    enquire.set_query(search_query)
    with ExecutionTime("enquire"):
        mset = enquire.get_mset(0, db.get_doccount())
        for m in mset:
            doc = m[xapian.MSET_DOCUMENT]
            print doc, doc.get_data()

if __name__ == "__main__":

    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = xapian.Database(pathname)

    axi = xapian.Database("/var/lib/apt-xapian-index/index")
    db.add_database(axi)

    parser = xapian.QueryParser()
    run_query(parser, sys.argv[1])
