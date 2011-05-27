
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

class ReviewsListModel(QAbstractListModel):

    # should match the softwarecenter.backend.reviews.Review attributes
    COLUMNS = ('_summary',
               '_review_text',
               '_rating',
               '_date_created',
               '_reviewer_displayname',
               )
 
    def __init__(self, parent=None):
        super(ReviewsListModel, self).__init__()
        self._reviews = []

        roles = dict(enumerate(ReviewsListModel.COLUMNS))
        self.setRoleNames(roles)
        # FIXME: make this async
        self.cache = get_pkg_info()
        self.reviews = get_review_loader(self.cache)

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._reviews)

    def data(self, index, role):
        if not index.isValid():
            return None
        review = self._reviews[index.row()]
        role = self.COLUMNS[role]
        return unicode(getattr(review, role[1:]))

    # helper
    def clear(self):
        self.beginRemoveRows(QModelIndex(), 0, self.rowCount()-1)
        self._reviews = []
        self.endRemoveRows()

    def _on_reviews_ready_callback(self, loader, reviews):
        self.beginInsertRows(QModelIndex(),
                             self.rowCount(), # first
                             self.rowCount() + len(reviews)) # last
        self._reviews += reviews
        self.endInsertRows()

    # getReviews interface (for qml)
    @Slot(str)
    def getReviews(self, pkgname, page=1):
        appname = ""
        # support pagination by not cleaning _reviews for subsequent pages
        if page == 1:
            self.clear()
        self.reviews.get_reviews(Application(appname, pkgname),
                                 self._on_reviews_ready_callback, 
                                 page)
    
