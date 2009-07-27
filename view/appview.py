#!/usr/bin/python

import logging
import gtk
import gobject
import apt
import os
import xapian
import time

XAPIAN_DATA_ICON = 0

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

    (COL_NAME, 
     COL_ICON,
     ) = range(2)
    column_type = (str, 
                   gtk.gdk.Pixbuf)

    def __init__(self, db, icons, search_term=""):
        gtk.GenericTreeModel.__init__(self)
        self.xapiandb = db
        self.icons = icons
        self.appnames = []
        if not search_term:
            for m in db.postlist(""):
                doc = db.get_document(m.docid)
                self.appnames.append(doc.get_data())
            self.appnames.sort()
        else:
            parser = xapian.QueryParser()
            user_query = parser.parse_query(search_term)
            #cat_query = xapian.Query("ACgame")
            #query = xapian.Query(xapian.Query.OP_AND, cat_query, user_query)
            enquire = xapian.Enquire(db)
            enquire.set_weighting_scheme(xapian.BoolWeight())
            enquire.set_query(user_query)
            matches = enquire.get_mset(0, 400)
            logging.debug("found ~%i matches" % matches.get_matches_estimated())
            for m in matches:
                doc = m[xapian.MSET_DOCUMENT]
                name = doc.get_data()
                self.appnames.append(name)
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
        if column == self.COL_NAME:
            return appname
        elif column == self.COL_ICON:
            try:
                icon_name = ""
                for post in self.xapiandb.postlist("AA"+appname):
                    doc = db.get_document(post.docid)
                    icon_name = doc.get_value(XAPIAN_DATA_ICON)
                    icon_name = os.path.splitext(icon_name)[0]
                    break
                if icon_name:
                    icon = self.icons.load_icon(icon_name, 24,0)
                    return icon
            except Exception, e:
                if not str(e).endswith("not present in theme"):
                    logging.exception("get_icon")
        return None
    def on_iter_next(self, rowref):
        #logging.debug("on_iter_next: %s" % rowref)
        new_rowref = rowref + 1
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

def on_entry_changed(widget, data):
    new_text = widget.get_text()
    print "on_entry_changed: ", new_text
    #if len(new_text) < 3:
    #    return
    (db, view) = data
    view.set_model(AppStore(db, icons, new_text))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # FIXME: use the apt-xapian-index database too as a additinal
    #        source (to avoid duplicating data)
    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the store
    store = AppStore(db, icons)

    # gui
    scroll = gtk.ScrolledWindow()

    view = gtk.TreeView()
    view.set_model(store)
    view.set_fixed_height_mode(True)

    tp = gtk.CellRendererPixbuf()
    column = gtk.TreeViewColumn("Icon", tp, pixbuf=store.COL_ICON)
    column.set_fixed_width(32)
    column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
    view.append_column(column)

    tr = gtk.CellRendererText()
    column = gtk.TreeViewColumn("Name", tr, markup=store.COL_NAME)
    column.set_fixed_width(200)
    column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
    view.append_column(column)

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
