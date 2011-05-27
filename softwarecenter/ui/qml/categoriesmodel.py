
import os

import gtk

from PySide.QtCore import QAbstractListModel, QModelIndex
from PySide.QtGui import QIcon

from softwarecenter.db.categories import CategoriesParser
from softwarecenter.db.database import StoreDatabase
from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.paths import XAPIAN_BASE_PATH

class CategoriesModel(QAbstractListModel):

    # should match the softwarecenter.backend.reviews.Review attributes
    COLUMNS = ('_name',
               '_iconname',
               )
 
    def __init__(self, parent=None):
        super(CategoriesModel, self).__init__()
        self._categories = []
        roles = dict(enumerate(CategoriesModel.COLUMNS))
        self.setRoleNames(roles)
        pathname = os.path.join(XAPIAN_BASE_PATH, "xapian")
        # FIXME: move this into app
        cache = get_pkg_info()
        db = StoreDatabase(pathname, cache)
        db.open()
        # /FIXME
        self.catparser = CategoriesParser(db)
        self._categories = self.catparser.parse_applications_menu(
            '/usr/share/app-install')

    # QAbstractListModel code
    def rowCount(self, parent=QModelIndex()):
        return len(self._categories)

    def data(self, index, role):
        if not index.isValid():
            return None
        cat = self._categories[index.row()]
        role = self.COLUMNS[role]
        if role == "_name":
            return cat.name
        elif role == "_iconname":
            # funny, but it appears like Qt does not have something
            # to lookup the icon path in QIcon
            icons = gtk.icon_theme_get_default()
            info = icons.lookup_icon(cat.iconname, 48, 0)
            return info.get_filename()
        

