
import locale
import xapian
from softwarestore.enums import *


class Application(object):
    """ a simple data object that contains just appname, pkgname
        and a sort method
    """
    __slots__ = ["appname", "pkgname"]
    def __init__(self, appname, pkgname):
        self.appname = appname
        self.pkgname = pkgname
    @staticmethod
    def apps_cmp(x, y):
        """ sort method for the applications """
        # sort(key=locale.strxfrm) would be more efficient, but its
        # currently broken, see http://bugs.python.org/issue2481
        return locale.strcoll(x.appname, y.appname)

class StoreDatabase(xapian.Database):
    """thin abstraction for the xapian database with convenient functions"""

    def __init__(self, pathname):
        xapian.Database.__init__(self, pathname)
        self.xapian_parser = xapian.QueryParser()
        self.xapian_parser.set_database(self)
        self.xapian_parser.add_boolean_prefix("pkg", "AP")
        self.xapian_parser.set_default_op(xapian.Query.OP_AND)

    def get_query_from_search_entry(self, search_term):
        """ get xapian.Query from a search term string """
        query = self.xapian_parser.parse_query(search_term, 
                                               xapian.QueryParser.FLAG_PARTIAL|
                                               xapian.QueryParser.FLAG_BOOLEAN)
        # FIXME: expand to add "AA" and "AP" before each search term?
        return query

    def get_xapian_document(self, appname, pkgname):
        """ Get the machting xapian document for appname, pkgname
        
        If no document is found, raise a IndexError
        """
        for m in self.postlist("AA"+appname):
            doc = self.get_document(m.docid)
            if doc.get_value(XAPIAN_VALUE_PKGNAME) == pkgname:
                return doc
        # no matching document found
        raise IndexError("No app '%s' for '%s' in database" % (appname,pkgname))

    def __len__(self):
        """return the doc count of the database"""
        return self.get_doccount()
