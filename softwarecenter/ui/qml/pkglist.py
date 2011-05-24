
import os
import sys

from PySide import QtCore
from PySide.QtCore import QObject, Property, QAbstractListModel, QModelIndex
from PySide.QtDeclarative import QDeclarativeItem

from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.enums import XAPIAN_VALUE_PKGNAME

class PkgListModel(QAbstractListModel):

    COLUMNS = ('_appname',
               '_pkgname',
               '_icon',
               '_summary',
               '_installed',
               '_description')
 
    def __init__(self, parent=None):
        super(PkgListModel, self).__init__()
        self._docs = []
        roles = dict(enumerate(PkgListModel.COLUMNS))
        self.setRoleNames(roles)
        self._query = ""
        # db
        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        # FIXME: make this async
        self.cache = get_pkg_info()
        self.cache.open()
        self.db = StoreDatabase(pathname, self.cache)
        self.db.open(use_axi=False)

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._docs)

    def data(self, index, role):
        if not index.isValid():
            return None
        doc = self._docs[index.row()]
        role = self.COLUMNS[role]
        pkgname = self.db.get_pkgname(doc)
        if role == "_pkgname":
            return pkgname 
        elif role == "_appname":
            return self.db.get_appname(doc)
        elif role == "_summary":
            return self.db.get_summary(doc)
        elif role == "_installed":
            if not pkgname in self.cache:
                return False
            return self.cache[pkgname].is_installed
        elif role == "_description":
            if not pkgname in self.cache:
                return ""
            return self.cache[pkgname].description
        elif role == "_icon":
            iconname = self.db.get_iconname(doc)
            return self._findIcon(iconname)
        return None

    # helper
    def _findIcon(self, iconname):
        path = "/usr/share/icons/Humanity/categories/32/applications-other.svg"
        for ext in ["svg", "png", ".xpm"]:
            p = "/usr/share/app-install/icons/%s" % iconname
            if os.path.exists(p+ext):
                path = "file://%s" % p+ext
                break
        return path
        
    def clear(self):
        self.beginRemoveRows(QModelIndex(), 0, self.rowCount()-1)
        self._docs = []
        self.endRemoveRows()

    def _runQuery(self, query):
        self.clear()
        docs = self.db.get_docs_from_query(str(query), start=0, end=100)
        self.beginInsertRows(QModelIndex(), len(docs), len(docs))
        self._docs = docs
        self.endInsertRows()

    # searchQuery property
    def getSearchQuery(self):
        return self._query
    def setSearchQuery(self, query):
        self._query = query
        self._runQuery(query)
    searchQueryChanged = QtCore.Signal()
    searchQuery = Property(unicode, getSearchQuery, setSearchQuery, notify=searchQueryChanged)
