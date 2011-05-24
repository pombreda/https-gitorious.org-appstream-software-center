#!/usr/bin/python

import glib
glib.threads_init()

import os
import sys

from PySide.QtCore import QUrl
from PySide.QtGui import QApplication
from PySide.QtDeclarative import qmlRegisterType, QDeclarativeView 

from pkglist import PkgListModel

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = QDeclarativeView()
    qmlpath = os.path.join(os.path.dirname(__file__), "sc.qml")
    view.setSource(QUrl.fromLocalFile(qmlpath))

    # ideally this should be part of the qml by using a qmlRegisterType()
    # but that does not seem to be supported in pyside yet(?) so we need
    # to cowboy it in here
    pkglistmodel = PkgListModel()
    rc = view.rootContext()
    rc.setContextProperty('pkglistmodel', pkglistmodel)

    # show it
    view.show()
    sys.exit(app.exec_())
