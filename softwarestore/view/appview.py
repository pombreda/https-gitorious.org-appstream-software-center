# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


import apt
import logging
import gtk
import gobject
import os
import pango
import sys
import time
import xapian

try:
    from appcenter.enums import *
except ImportError:
    # support running from the dir too
    d = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(),__file__)))
    sys.path.insert(0, os.path.split(d)[0])
    from enums import *

class ExecutionTime(object):
    """
    Helper that can be used in with statements to have a simple
    measure of the timming of a particular block of code, e.g.
    with ExecutinTime("db flush"):
        db.flush()
    """
    def __init__(self, info=""):
        self.info = info
    def __enter__(self):
        self.now = time.time()
    def __exit__(self, type, value, stack):
        print "%s: %s" % (self.info, time.time() - self.now)

class AppStore(gtk.GenericTreeModel):
    """ 
    A subclass GenericTreeModel that reads its data from a xapian
    database. It can combined with any xapian querry and with
    a generic filter function (that can filter on data not
    available in xapian)
    """

    (COL_APP_NAME,
     COL_TEXT, 
     COL_ICON,
     ) = range(3)

    column_type = (str, 
                   str,
                   gtk.gdk.Pixbuf)

    ICON_SIZE = 24

    def __init__(self, db, icons, search_query=None, limit=200, 
                 sort=False, filter=None):
        """
        Initalize a AppStore. 

        :Parameters: 
        - `db`: a xapian.Database that contians the applications
        - `icons`: a gtk.IconTheme that contains the icons
        - `search_query`: a search as a xapian.Query 
        - `limit`: how many items the search should return (0 == unlimited)
        - `sort`: sort alphabetically after a search
                   (default is to use relevance sort)
        - `filter`: filter functions that can be used to filter the 
                    data further. A python function that gets a pkgname
        """
        gtk.GenericTreeModel.__init__(self)
        self.xapiandb = db
        self.icons = icons
        self.appnames = []
        self.filter = filter
        if not search_query:
            # limit to applications
            for m in db.postlist("ATapplication"):
                doc = db.get_document(m.docid)
                if filter and self.is_filtered_out(filter, doc):
                    continue
                self.appnames.append(doc.get_data())
            self.appnames.sort()
        else:
            enquire = xapian.Enquire(db)
            enquire.set_query(search_query)
            enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
            if limit == 0:
                matches = enquire.get_mset(0, db.get_doccount())
            else:
                matches = enquire.get_mset(0, limit)
            logging.debug("found ~%i matches" % matches.get_matches_estimated())
            for m in matches:
                doc = m[xapian.MSET_DOCUMENT]
                if "APPVIEW_DEBUG_TERMS" in os.environ:
                    print doc.get_data()
                    for t in doc.termlist():
                        print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
                    print "\n"
                appname = doc.get_data()
                if filter and self.is_filtered_out(filter, doc):
                    continue
                self.appnames.append(appname)
            if sort:
                self.appnames.sort(key=str.lower)
    def is_filtered_out(self, filter, doc):
        """ apply filter and return True if the package is filtered out """
        pkgname = doc.get_value(XAPIAN_VALUE_PKGNAME)
        return not filter.filter(doc, pkgname)
    # GtkTreeModel functions
    def on_get_flags(self):
        return (gtk.TREE_MODEL_LIST_ONLY|
                gtk.TREE_MODEL_ITERS_PERSIST)
    def on_get_n_columns(self):
        return len(self.column_type)
    def on_get_column_type(self, index):
        return self.column_type[index]
    def on_get_iter(self, path):
        logging.debug("on_get_iter: %s" % path)
        if len(self.appnames) == 0:
            return None
        index = path[0]
        return index
    def on_get_path(self, rowref):
        logging.debug("on_get_path: %s" % rowref)
        return rowref
    def on_get_value(self, rowref, column):
        #logging.debug("on_get_value: %s %s" % (rowref, column))
        appname = self.appnames[rowref]
        if column == self.COL_APP_NAME:
            return appname
        elif column == self.COL_TEXT:
            for post in self.xapiandb.postlist("AA"+appname):
                doc = self.xapiandb.get_document(post.docid)
                summary = doc.get_value(XAPIAN_VALUE_SUMMARY)
            s = "%s\n<small>%s</small>" % (gobject.markup_escape_text(appname),
                                   gobject.markup_escape_text(summary))
            return s
        elif column == self.COL_ICON:
            try:
                icon_name = ""
                for post in self.xapiandb.postlist("AA"+appname):
                    doc = self.xapiandb.get_document(post.docid)
                    icon_name = doc.get_value(XAPIAN_VALUE_ICON)
                    icon_name = os.path.splitext(icon_name)[0]
                    break
                if icon_name:
                    icon = self.icons.load_icon(icon_name, self.ICON_SIZE,0)
                    return icon
            except Exception, e:
                if not (str(e).endswith("not present in theme") or
                        str(e).endswith("Unrecognized image file format")):
                    logging.exception("get_icon")
        return self.icons.load_icon(MISSING_APP_ICON, self.ICON_SIZE, 0)
    def on_iter_next(self, rowref):
        #logging.debug("on_iter_next: %s" % rowref)
        new_rowref = int(rowref) + 1
        if new_rowref >= len(self.appnames):
            return None
        return new_rowref
    def on_iter_children(self, parent):
        if parent:
            return None
        return self.appnames[0]
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        logging.debug("on_iter_n_children: %s (%i)" % (rowref, len(self.appnames)))
        if rowref:
            return 0
        return len(self.appnames)
    def on_iter_nth_child(self, parent, n):
        logging.debug("on_iter_nth_child: %s %i" % (parent, n))
        if parent:
            return 0
        try:
            return self.appnames[n]
        except IndexError, e:
            return None
    def on_iter_parent(self, child):
        return None

# custom renderer for the arrow thing that mpt wants
class CellRendererTextWithActivateArrow(gtk.CellRendererText):
    
    # padding around the arrow at the end
    ARROW_PADDING = 4

    def __init__(self):
        gtk.CellRendererText.__init__(self)
        icons = gtk.icon_theme_get_default()
        self._arrow_space = AppStore.ICON_SIZE + self.ARROW_PADDING
        self._forward = icons.load_icon("gtk-go-forward-ltr", 
                                        AppStore.ICON_SIZE, 0)
    def do_render(self, window, widget, background_area, cell_area, 
                  expose_area, flags):
        # reserve space at the end for the arrow
        cell_area.width -= self._arrow_space
        gtk.CellRendererText.do_render(self, window, widget, background_area, 
                                       cell_area, expose_area, flags)
        # now render the arrow if its selected
        # FIXME: should we show the arrow on gtk.CELL_RENDERER_PRELIT too?
        if gtk.CELL_RENDERER_SELECTED & flags:
            (x, y, width, height, depth) = window.get_geometry()
            dest_x = cell_area.x + cell_area.width
            dest_y = (cell_area.y + 
                      int(((cell_area.height - AppStore.ICON_SIZE)/2.0)))
            window.draw_pixbuf(None, 
                               self._forward,   # icon
                               0, 0,            # src pixbuf
                               dest_x, dest_y,  # dest in window
                               -1, -1,          # size
                               0, 0, 0)         # dither
gobject.type_register(CellRendererTextWithActivateArrow)


class AppView(gtk.TreeView):
    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE, 
                                   (str, ),
                                  )
    }

    def __init__(self, store):
        gtk.TreeView.__init__(self)
        self.set_fixed_height_mode(True)
        self.set_headers_visible(False)
        tp = gtk.CellRendererPixbuf()
        column = gtk.TreeViewColumn("Icon", tp, pixbuf=AppStore.COL_ICON)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        tr = CellRendererTextWithActivateArrow()
        tr.set_property("ellipsize", pango.ELLIPSIZE_MIDDLE)
        column = gtk.TreeViewColumn("Name", tr, markup=AppStore.COL_TEXT)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)
        self.set_model(store)
        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated)
        # button and motion are "special" 
        self.connect("button-press-event", self._on_button_press_event)
        self.connect("motion-notify-event", self._on_motion_notify_event)
    def _on_row_activated(self, treeview, path, column):
        (name, text, icon) = treeview.get_model()[path]
        self.emit("application-activated", name)
    def _on_motion_notify_event(self, widget, event):
        (rel_x, rel_y, width, height, depth) = widget.window.get_geometry()
        if width - event.x <= AppStore.ICON_SIZE:
            self.window.set_cursor(self._cursor_hand)
        else:
            self.window.set_cursor(None)
    def _on_button_press_event(self, widget, event):
        if event.button != 1:
            return
        res = self.get_path_at_pos(event.x, event.y)
        if not res:
            return
        (path, column, wx, wy) = res
        if path is None:
            return
        # only act when the selection is already there 
        selection = widget.get_selection()
        if not selection.path_is_selected(path):
            return
        # get the size of gdk window
        (rel_x, rel_y, width, height, depth) = widget.window.get_geometry()
        # the last pixels of the view are reserved for the arrow icon
        if width - event.x <= AppStore.ICON_SIZE:
            self.emit("row-activated", path, column)

# XXX should we use a xapian.MatchDecider instead?
class AppViewFilter(object):
    """ 
    Filter that can be hooked into AppStore to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, cache):
        self.cache = cache
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def filter(self, doc, pkgname):
        """return True if the package should be displayed"""
        logging.debug("filter: supported_only: %s installed_only: %s '%s'" % (
                self.supported_only, self.installed_only, pkgname))
        if self.installed_only:
            if (self.cache.has_key(pkgname) and 
                not self.cache[pkgname].isInstalled):
                return False
        if self.not_installed_only:
            if (self.cache.has_key(pkgname) and 
                self.cache[pkgname].isInstalled):
                return False
        # FIXME: add special property to the desktop file instead?
        #        what about in the future when we support pkgs without
        #        desktop files?
        if self.supported_only:
            section = doc.get_value(XAPIAN_VALUE_ARCHIVE_SECTION)
            if section != "main" and section != "restricted":
                return False
        return True

def get_query_from_search_entry(search_term):
    # now build a query
    parser = xapian.QueryParser()
    user_query = parser.parse_query(search_term)
    # ensure that we only search for applicatins here, even
    # when a-x-i is loaded
    app_query =  xapian.Query("ATapplication")
    query = xapian.Query(xapian.Query.OP_AND, app_query, user_query)
    return query

def on_entry_changed(widget, data):
    new_text = widget.get_text()
    print "on_entry_changed: ", new_text
    #if len(new_text) < 3:
    #    return
    (db, view) = data
    query = get_query_from_search_entry(new_text)
    view.set_model(AppStore(db, icons, query))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # add the apt-xapian-database for here (we don't do this
    # for now as we do not have a good way to integrate non-apps
    # with the UI)
    #axi = xapian.Database("/var/lib/apt-xapian-index/index")
    #db.add_database(axi)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the store
    import apt
    cache = apt.Cache(apt.progress.OpTextProgress())
    filter = AppViewFilter(cache)
    filter.set_supported_only(True)
    store = AppStore(db, icons, filter=filter)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (db, view))

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()
