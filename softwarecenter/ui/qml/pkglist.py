
import os
import sys

from PySide import QtCore
from PySide.QtCore import QObject, Property, QAbstractListModel, QModelIndex, Slot
from PySide.QtDeclarative import QDeclarativeItem

from softwarecenter.db.database import StoreDatabase, Application
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.paths import XAPIAN_BASE_PATH
from softwarecenter.enums import XAPIAN_VALUE_PKGNAME
from softwarecenter.backend import get_install_backend
from softwarecenter.backend.reviews import get_review_loader

class PkgListModel(QAbstractListModel):

    COLUMNS = ('_appname',
               '_pkgname',
               '_icon',
               '_summary',
               '_installed',
               '_description',
               '_ratings_total',
               '_ratings_average',
               '_installremoveprogress')
 
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
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", 
                             self._on_backend_transaction_progress_changed)
        self.reviews = get_review_loader(self.cache)

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._docs)

    def data(self, index, role):
        if not index.isValid():
            return None
        doc = self._docs[index.row()]
        role = self.COLUMNS[role]
        pkgname = unicode(self.db.get_pkgname(doc))
        appname =  unicode(self.db.get_appname(doc))
        if role == "_pkgname":
            return pkgname 
        elif role == "_appname":
            return appname
        elif role == "_summary":
            return unicode(self.db.get_summary(doc))
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
        elif role == "_ratings_average":
            stats = self.reviews.get_review_stats(Application(appname, pkgname))
            if stats:
                return stats.ratings_average
            return 0
        elif role == "_ratings_total":
            stats = self.reviews.get_review_stats(Application(appname, pkgname))
            if stats:
                return stats.ratings_total
            return 0
        elif role == "_installremoveprogress":
            if pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[pkgname].progress
            return -1
        return None

    # helper
    def _on_backend_transaction_progress_changed(self, backend, pkgname, progress):
        column = self.COLUMNS.index("_installremoveprogress")
        # FIXME: instead of the entire model, just find the row that changed
        top = self.createIndex(0, column)
        bottom = self.createIndex(self.rowCount()-1, column)
        self.dataChanged.emit(top, bottom)

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

    # install/remove interface (for qml)
    @Slot(str)
    def installPackage(self, pkgname):
        appname = ""
        iconname = ""
        self.backend.install(pkgname, appname, iconname)
    @Slot(str)
    def removePackage(self, pkgname):
        appname = ""
        iconname = ""
        self.backend.remove(pkgname, appname, iconname)

    # searchQuery property (for qml )
    def getSearchQuery(self):
        return self._query
    def setSearchQuery(self, query):
        self._query = query
        self._runQuery(query)
    searchQueryChanged = QtCore.Signal()
    searchQuery = Property(unicode, getSearchQuery, setSearchQuery, notify=searchQueryChanged)
