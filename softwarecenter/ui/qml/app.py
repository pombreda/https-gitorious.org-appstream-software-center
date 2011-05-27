#!/usr/bin/python

import glib
glib.threads_init()

import os
import sys

from PySide import QtDeclarative
from PySide.QtCore import QUrl
from PySide.QtGui import QApplication
from PySide.QtDeclarative import qmlRegisterType, QDeclarativeView 

from softwarecenter.db.pkginfo import get_pkg_info

from pkglist import PkgListModel
from reviewslist import ReviewsListModel
from categoriesmodel import CategoriesModel

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # TODO do this async
    app.cache = get_pkg_info()
    app.cache.open()

    view = QDeclarativeView()
    view.setResizeMode(QtDeclarative.QDeclarativeView.SizeRootObjectToView)

    # ideally this should be part of the qml by using a qmlRegisterType()
    # but that does not seem to be supported in pyside yet(?) so we need
    # to cowboy it in here
    pkglistmodel = PkgListModel()
    reviewslistmodel = ReviewsListModel()
    categoriesmodel = CategoriesModel()
    rc = view.rootContext()
    rc.setContextProperty('pkglistmodel', pkglistmodel)
    rc.setContextProperty('reviewslistmodel', reviewslistmodel)
    rc.setContextProperty('categoriesmodel', categoriesmodel)

    # debug
    if len(sys.argv) > 1:
        # FIXME: we really should set the text entry here
        pkglistmodel.setSearchQuery(sys.argv[1])

    # load the main QML file into the view
    qmlpath = os.path.join(os.path.dirname(__file__), "sc.qml")
    view.setSource(QUrl.fromLocalFile(qmlpath))

    # show it
    view.show()
    sys.exit(app.exec_())
