import sys

import glib
glib.threads_init()

# pyside are the official bindings, LGPL
from PySide import QtCore
from PySide import QtGui

from PySide.QtCore import *
from PySide.QtGui import *

from PySide import QtDeclarative
#~ from PySide import QtOpenGL

import os
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.paths import XAPIAN_BASE_PATH

class PropWrapper(QtCore.QObject):
    def __init__(self, xdb, xdoc):
        QtCore.QObject.__init__(self)
        self._xdoc = xdoc
        self._xapiandb = xdb
    def _name(self):
        return self._xapiandb.get_pkgname(self._xdoc)
    def _icon(self):
        icon = self._xapiandb.get_iconname(self._xdoc)
        # FIXME: use icontheme
        path = "/usr/share/icons/Humanity/categories/32/applications-other.svg"
        for ext in ["svg", "png", ".xpm"]:
            p = "/usr/share/app-install/icons/%s" % icon
            if os.path.exists(p+ext):
                path = "file://%s" % p+ext
                break
        return path
 
    changed = QtCore.Signal()
    name = QtCore.Property(unicode, _name, notify=changed)
    icon = QtCore.Property(unicode, _icon, notify=changed)


class ListModel(QtCore.QAbstractListModel):
    COLUMNS = ('pkg',)
 
    def __init__(self):
        QtCore.QAbstractListModel.__init__(self)
        self._items = []
        self.setRoleNames(dict(enumerate(ListModel.COLUMNS)))
 
    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self._items)
 
    def data(self, index, role):
        if index.isValid() and role == ListModel.COLUMNS.index('pkg'):
            return self._items[index.row()]
        return None

    def clear(self):
        self.removeRows(0, self.rowCount())
        return

    def removeRows(self, row, count, parent=QModelIndex()):
        # make sure the index is valid, to avoid IndexErrors ;)
        if row < 0 or row > len(self._items):
            return

        # let the model know we're changing things.
        # we may have to remove multiple rows, if not, this could be handled simpler.
        self.beginRemoveRows(parent, row, row + count - 1)

        # actually remove the items from our internal data representation
        while count != 0:
            del self._items[row]
            count -= 1

        # let the model know we're done
        self.endRemoveRows()

    def addItem(self, item):
        # The str() cast is because we don't want to be storing a Qt type in here.
        self.beginInsertRows(QModelIndex(), len(self._items), len(self._items))
        self._items.append(item)
        self.endInsertRows()


class Controller(QtCore.QObject):

    def __init__(self, db, pkg_list):
        QtCore.QObject.__init__(self)
        self._db = db
        self._pkglist = pkg_list
        self._previous_query = None

    @QtCore.Slot(QtCore.QObject)
    def rowClicked(self, wrapper):
        print 'User clicked on:', wrapper._prop.name

    @QtCore.Slot(str)
    def rebuildListFromQuery(self, s):
        if str(s) == self._previous_query: return
        self._previous_query = str(s)

        docs = self._db.get_docs_from_query(str(s))

        self._pkglist.clear()
        for xdoc in docs:
            o = PropWrapper(self._db, xdoc)
            self._pkglist.addItem(o)
        return

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    m = QtGui.QMainWindow()

    view = QtDeclarative.QDeclarativeView()
    view.setResizeMode(QtDeclarative.QDeclarativeView.SizeRootObjectToView)

    cache = get_pkg_info()
    pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    pkglist = ListModel()
    controller = Controller(db, pkglist)
    
    rc = view.rootContext()
    rc.setContextProperty('controller', controller)
    rc.setContextProperty('pythonListModel', pkglist)

    view.setSource(os.path.join(os.path.dirname(__file__), 'appview.qml'))
    m.setCentralWidget(view) 
    m.show()
 
    app.exec_()
