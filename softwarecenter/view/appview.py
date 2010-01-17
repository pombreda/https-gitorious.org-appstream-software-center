# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
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
import locale
import logging
import glib
import gobject
import gtk
import os
import pango
import sys
import time
import xapian

if os.path.exists("./softwarecenter/enums.py"):
    sys.path.insert(0, ".")
from softwarecenter.enums import *
from softwarecenter.utils import *
from softwarecenter.db.database import StoreDatabase, Application
#from softwarecenter.backend.aptd import AptdaemonBackend as InstallBackend

from gettext import gettext as _

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
     COL_INSTALLED_OVERLAY,
     COL_PKGNAME,
     IS_ACTIVE
     ) = range(6)

    column_type = (str,
                   str,
                   gtk.gdk.Pixbuf,
                   bool,
                   str,
                   int)

    ICON_SIZE = 24

    (SEARCHES_SORTED_BY_POPCON,
     SEARCHES_SORTED_BY_XAPIAN_RELEVANCE,
     SEARCHES_SORTED_BY_ALPHABETIC) = range(3)

    def __init__(self, cache, db, icons, search_query=None, limit=200,
                 sort=False, filter=None):
        """
        Initalize a AppStore.

        :Parameters:
        - `cache`: apt cache (for stuff like the overlay icon)
        - `db`: a xapian.Database that contians the applications
        - `icons`: a gtk.IconTheme that contains the icons
        - `search_query`: a single search as a xapian.Query or a list
        - `limit`: how many items the search should return (0 == unlimited)
        - `sort`: sort alphabetically after a search
                   (default is to use relevance sort)
        - `filter`: filter functions that can be used to filter the
                    data further. A python function that gets a pkgname
        """
        gtk.GenericTreeModel.__init__(self)
        self.cache = cache
        self.db = db
        self.icons = icons
        self.apps = []
        self.apps_activity = []
        self.sorted = sort
        self.filter = filter
        self._searches_sort_mode = self._get_searches_sort_mode()
        if not search_query:
            # limit to applications
            for m in db.xapiandb.postlist("ATapplication"):
                doc = db.xapiandb.get_document(m.docid)
                if filter and self.is_filtered_out(filter, doc):
                    continue
                appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                # eh, how do i get real popcorn values not unicodes???
                #print repr(doc.get_value(XAPIAN_VALUE_POPCON))
                pkgname = db.get_pkgname(doc)
                self.apps.append(Application(appname, pkgname))
                self.apps_activity.append(0)
            self.apps.sort()
        else:
            # we support single and list search_queries,
            # if list we append them one by one
            if isinstance(search_query, xapian.Query):
                search_query = [search_query]
            already_added = set()
            for q in search_query:
                logging.debug("using query: '%s'" % q)
                enquire = xapian.Enquire(db.xapiandb)
                enquire.set_query(q)
                # set search order mode
                if self._searches_sort_mode == self.SEARCHES_SORTED_BY_POPCON:
                    enquire.set_sort_by_value_then_relevance(XAPIAN_VALUE_POPCON)
                elif self._searches_sort_mode == self.SEARCHES_SORTED_BY_ALPHABETIC:
                    self.sorted=sort=True
                if limit == 0:
                    matches = enquire.get_mset(0, len(db))
                else:
                    matches = enquire.get_mset(0, limit)
                logging.debug("found ~%i matches" % matches.get_matches_estimated())
                for m in matches:
                    doc = m[xapian.MSET_DOCUMENT]
                    if "APPVIEW_DEBUG_TERMS" in os.environ:
                        print doc.get_value(XAPIAN_VALUE_APPNAME)
                        for t in doc.termlist():
                            print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
                        print "\n"
                    appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                    pkgname = db.get_pkgname(doc)
                    if filter and self.is_filtered_out(filter, doc):
                        continue
                    # when doing multiple queries we need to ensure
                    # we don't add duplicates
                    app = Application(appname, pkgname)
                    if not app in already_added:
                        self.apps.append(app)
                        self.apps_activity.append(0)
                        already_added.add(app)
            if sort:
                self.apps.sort()

    def is_filtered_out(self, filter, doc):
        """ apply filter and return True if the package is filtered out """
        pkgname = self.db.get_pkgname(doc)
        return not filter.filter(doc, pkgname)
    # internal helper
    def _get_searches_sort_mode(self):
        mode = self.SEARCHES_SORTED_BY_POPCON
        if "SOFTWARE_CENTER_SEARCHES_SORT_MODE" in os.environ:
            k = os.environ["SOFTWARE_CENTER_SEARCHES_SORT_MODE"].strip().lower()
            if k == "popcon":
                mode = self.SEARCHES_SORTED_BY_POPCON
            elif k == "alphabetic":
                mode = self.SEARCHES_SORTED_BY_ALPHABETIC
            elif k == "xapian":
                mode = self.SEARCHES_SORTED_BY_XAPIAN_RELEVANCE
        return mode
    # GtkTreeModel functions
    def on_get_flags(self):
        return (gtk.TREE_MODEL_LIST_ONLY|
                gtk.TREE_MODEL_ITERS_PERSIST)
    def on_get_n_columns(self):
        return len(self.column_type)
    def on_get_column_type(self, index):
        return self.column_type[index]
    def on_get_iter(self, path):
        #logging.debug("on_get_iter: %s" % path)
        if len(self.apps) == 0:
            return None
        index = path[0]
        return index
    def on_get_path(self, rowref):
        logging.debug("on_get_path: %s" % rowref)
        return rowref
    def on_get_value(self, rowref, column):
        #logging.debug("on_get_value: %s %s" % (rowref, column))
        app = self.apps[rowref]
        doc = self.db.get_xapian_document(app.appname, app.pkgname)
        if column == self.COL_APP_NAME:
            return app.appname
        elif column == self.COL_TEXT:
            appname = app.appname
            if not appname:
                appname = app.pkgname
            summary = self.db.get_summary(doc)
            if self.db.is_appname_duplicated(appname):
                appname = "%s (%s)" % (appname, app.pkgname)
            s = "%s\n<small>%s</small>" % (
                gobject.markup_escape_text(appname),
                gobject.markup_escape_text(summary))
            return s
        elif column == self.COL_ICON:
            try:
                icon_name = doc.get_value(XAPIAN_VALUE_ICON)
                if icon_name:
                    icon_name = os.path.splitext(icon_name)[0]
                    icon = self.icons.load_icon(icon_name, self.ICON_SIZE, 0)
                    return icon
            except glib.GError, e:
                logging.debug("get_icon returned '%s'" % e)
            return self.icons.load_icon(MISSING_APP_ICON, self.ICON_SIZE, 0)
        elif column == self.COL_INSTALLED_OVERLAY:
            pkgname = self.db.get_pkgname(doc)
            if self.cache.has_key(pkgname) and self.cache[pkgname].isInstalled:
                return True
            return False
        elif column == self.COL_PKGNAME:
            pkgname = self.db.get_pkgname(doc)
            return pkgname
        elif column == self.IS_ACTIVE:
            try:
                is_active = self.apps_activity[rowref]
            except:
                return 0
            return is_active
    def on_iter_next(self, rowref):
        #logging.debug("on_iter_next: %s" % rowref)
        new_rowref = int(rowref) + 1
        if new_rowref >= len(self.apps):
            return None
        return new_rowref
    def on_iter_children(self, parent):
        if parent:
            return None
        # rowref of the first element, so we return zero here
        return 0
    def on_iter_has_child(self, rowref):
        return False
    def on_iter_n_children(self, rowref):
        logging.debug("on_iter_n_children: %s (%i)" % (rowref, len(self.apps)))
        if rowref:
            return 0
        return len(self.apps)
    def on_iter_nth_child(self, parent, n):
        logging.debug("on_iter_nth_child: %s %i" % (parent, n))
        if parent:
            return 0
        if n >= len(self.apps):
            return None
        return n
    def on_iter_parent(self, child):
        return None

    def set_activity(self, rowref, value):
        try:
            self.apps_activity[rowref] = value
            self.row_changed(rowref, self.get_iter(rowref))
        except:
            pass
        return


class CellRendererAppView(gtk.GenericCellRenderer):

    __gproperties__ = {
        'markup': (gobject.TYPE_STRING, 'Markup', 'Pango markup', '',
            gobject.PARAM_READWRITE),

#        'addons': (gobject.TYPE_INT, 'AddOns', 'Has add-ons?', 0, 2, 0,
#            gobject.PARAM_READWRITE),

#        'rating': (gobject.TYPE_INT, 'Rating', 'Popcorn rating', 0, 5, 0,
#            gobject.PARAM_READWRITE),

#        'reviews': (gobject.TYPE_INT, 'Reviews', 'Number of reviews', 0, 100, 0,
#            gobject.PARAM_READWRITE),

        'isactive': (gobject.TYPE_INT, 'IsActive', 'Is active?', 0, 2, 0,
            gobject.PARAM_READWRITE),

        'installed': (bool, 'installed', 'Is the app installed', False,
                     gobject.PARAM_READWRITE),
        }

    def __init__(self, show_ratings):
        self.__gobject_init__()
        self.markup = None
        self.rating = 5
        self.reviews = 1
        self.isactive = 0
        self.installed = False
        self.show_ratings = show_ratings
        return

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def draw_appname_summary(self, window, widget, cell_area, xpad, ypad, layout, flags):
        # work out where to draw layout
        dst_x = cell_area.x + xpad
        dst_y = cell_area.y + ypad

        w = widget.star_pixbuf.get_width()
        h = widget.star_pixbuf.get_height()
        max_star_width = 5*(w+1) + xpad

        # work out layouts max width
        if layout.get_pixel_extents()[1][2] >= cell_area.width-cell_area.y-2*xpad - max_star_width:
            layout.set_width((cell_area.width - 3*xpad - max_star_width)*pango.SCALE)

        widget.style.paint_layout(window,
                                  flags,
                                  True,
                                  cell_area,
                                  widget,
                                  None,
                                  dst_x,
                                  dst_y,
                                  layout)
        return w, h

    def draw_rating(self, window, widget, cell_area, xpad, ypad, layout, w, h, flags):
       # draw star rating
        dest_x = cell_area.width-xpad 
        for i in range(self.rating):
            window.draw_pixbuf(None,
                               widget.star_pixbuf,    # icon
                               0, 0,                # src pixbuf
                               dest_x - (self.rating-i)*(w+1) + 32,  # xdest
                               cell_area.y+1+ypad,    # ydest
                               -1, -1,              # size
                               0, 0, 0)             # dither

        # draw number of reviews
        if self.reviews != 1:
            s = 's'
        elif self.reviews:
            s = ''

        layout.set_markup("<small>%s review%s</small>" % (self.reviews, s))
        lw = layout.get_pixel_extents()[1][2]
        dest_x = dest_x - 5*(w+1) + 32 + (5*(w+1)-lw)/2

        widget.style.paint_layout(window,
                                  flags,
                                  True,
                                  cell_area,
                                  widget,
                                  None,
                                  dest_x,
                                  cell_area.y+ypad+h+1,
                                  layout)
        return

    def draw_button(self, window, widget, cell_area, xpad, ypad, layout, dst_x, dst_y, bw, bh, lw, lh):
        widget.style.paint_box(window,
                               gtk.STATE_NORMAL,
                               gtk.SHADOW_ETCHED_OUT,
                               cell_area,
                               widget,
                               "button",
                               dst_x,       # x
                               dst_y,       # y
                               bw,          # width
                               bh)          # height

        # draw Install button label
        widget.style.paint_layout(window,
                            gtk.STATE_NORMAL,
                            True,
                            cell_area,
                            widget,
                            None,
                            dst_x + (bw-lw)/2,
                            dst_y + (bh-lh)/2,
                            layout)
        return

    def on_render(self, window, widget, background_area, cell_area,
        expose_area, flags):

        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')

        # create pango layout with markup
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.markup)
        layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        w, h = self.draw_appname_summary(window, widget, cell_area, xpad, ypad, layout, flags)

        if self.show_ratings:
            self.draw_rating(window, widget, cell_area, xpad, ypad, layout, w, h, flags)

        if not self.isactive: return
        # else draw buttons

        # Install button
        # label and label size
        layout.set_markup("<small>Install</small>")
        lw = layout.get_pixel_extents()[1][2]
        lh = layout.get_pixel_extents()[1][3]

        # button size
        bw0 = lw+10*xpad # install button should have more padding, cos of importance?
        bh = lh+4*ypad

        dst_x0 = cell_area.width-xpad+32 - bw0
        dst_y = cell_area.y+36+(32-bh)/2

        if self.installed:
            layout.set_markup("<small>Remove</small>")
            lw = layout.get_pixel_extents()[1][2]

        self.draw_button(window,
                 widget,
                 cell_area,
                 xpad, ypad,
                 layout,
                 dst_x0, dst_y,
                 bw0, bh,
                 lw, lh)

#        # Choose Add-Ons... button
#        # label and label size
#        layout.set_markup("<small>Choose Add-Ons...</small>")
#        lw = layout.get_pixel_extents()[1][2]

#        # button size
#        bw1 = lw+4*xpad
#        dst_x1 = dst_x0 - bw1 - 3*xpad

#        self.draw_button(window, widget, cell_area, xpad, ypad, layout, dst_x1, dst_y, bw1, bh, lw, lh)

        # More Info button
        # label and label size
        layout.set_markup("<small>More Info</small>")
        lw = layout.get_pixel_extents()[1][2]

        # button size
        bw2 = lw+3*xpad
        dst_x2 = cell_area.x + xpad

        self.draw_button(window,
                         widget,
                         cell_area,
                         xpad, ypad,
                         layout,
                         dst_x2, dst_y,
                         bw2, bh,
                         lw, lh)

        if widget.btn_regions: return

        # specify button regions
        widget.btn_regions = []
        widget.btn_regions.append((dst_x0, dst_y, bw0, bh, 'install'))
        #widget.btn_regions.append((dst_x1, dst_y, bw1, bh, 'addons'))
        widget.btn_regions.append((dst_x2, dst_y, bw2, bh, 'info'))
        return

    def on_get_size(self, widget, cell_area):
        h = 36
        if self.isactive: h += 32
        return -1, -1, -1, h

gobject.type_register(CellRendererAppView)


# custom renderer for the arrow thing that mpt wants
class CellRendererPixbufWithOverlay(gtk.CellRendererPixbuf):

    # offset of the install overlay icon
    OFFSET_X = 14
    OFFSET_Y = 16

    # size of the install overlay icon
    OVERLAY_SIZE = 16

    __gproperties__ = {
        'overlay' : (bool, 'overlay', 'show an overlay icon', False,
                     gobject.PARAM_READWRITE),
   }

    def __init__(self, overlay_icon_name):
        gtk.CellRendererPixbuf.__init__(self)
        icons = gtk.icon_theme_get_default()
        self.overlay = False
        try:
            self._installed = icons.load_icon(overlay_icon_name,
                                          self.OVERLAY_SIZE, 0)
        except glib.GError:
            # icon not present in theme, probably because running uninstalled
            self._installed = icons.load_icon('emblem-system',
                                          self.OVERLAY_SIZE, 0)
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def do_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):
        gtk.CellRendererPixbuf.do_render(self, window, widget, background_area,
                                         cell_area, expose_area, flags)
        overlay = self.get_property("overlay")
        if overlay:
            dest_x = cell_area.x + self.OFFSET_X
            dest_y = cell_area.y + self.OFFSET_Y
            window.draw_pixbuf(None,
                               self._installed, # icon
                               0, 0,            # src pixbuf
                               dest_x, dest_y,  # dest in window
                               -1, -1,          # size
                               0, 0, 0)         # dither
gobject.type_register(CellRendererPixbufWithOverlay)


class AppView(gtk.TreeView):
    """Treeview based view component that takes a AppStore and displays it"""

    __gsignals__ = {
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
    }

    def __init__(self, show_ratings, store=None):
        gtk.TreeView.__init__(self)
        # previous active row reference
        self.prev = 0
        self.btn_regions = None

        #self.set_fixed_height_mode(True)
        self.set_headers_visible(False)
        tp = CellRendererPixbufWithOverlay("software-center-installed")
        column = gtk.TreeViewColumn("Icon", tp,
                                    pixbuf=AppStore.COL_ICON,
                                    overlay=AppStore.COL_INSTALLED_OVERLAY)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)


        filename = "/usr/share/icons/Humanity/emblems/16/emblem-favorite.svg"
        self.star_pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
        tr = CellRendererAppView(show_ratings)
        tr.set_property('xpad', 3)
        tr.set_property('ypad', 2)

        column = gtk.TreeViewColumn("Apps", tr, markup=AppStore.COL_TEXT, isactive=AppStore.IS_ACTIVE, installed=AppStore.COL_INSTALLED_OVERLAY)
        column.set_fixed_width(200)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        if store is None:
            store = gtk.ListStore(str, gtk.gdk.Pixbuf)
        self.set_model(store)

        # custom cursor
        self._cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # our own "activate" handler
        self.connect("row-activated", self._on_row_activated)
        # button and motion are "special"

        self.connect("button-press-event", self._on_button_press_event, column)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("motion-notify-event", self._on_motion, tr, column)

    def _on_motion(self, tree, event, tr, col):
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y) or not self.btn_regions:
            self.window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path: return
        yO = tree.get_cell_area(path[0], col).y
        for cx, cy, cw, ch, name in self.btn_regions:
            rect = gtk.gdk.Rectangle(cx, yO+cy, cw, ch)
            rr = gtk.gdk.region_rectangle(rect)

            if rr.point_in(x, y):
                self.window.set_cursor(self._cursor_hand)
                break
            else:
                self.window.set_cursor(None)
        return

    def _on_cursor_changed(self, tree):
        model = tree.get_model()
        try:
            model.set_activity(self.prev, 0)
        except:
            pass

        path = tree.get_cursor()[0][0]
        model.set_activity(path, 1)

        self.prev = path

        selection = tree.get_selection()
        (model, it) = selection.get_selected()
        if it is None:
            return
        (name, text, icon, overlay, pkgname, isactive) = model[it]
        self.emit("application-selected", Application(name, pkgname))
        return

    def _on_row_activated(self, treeview, path, column):
        (name, text, icon, overlay, pkgname, isactive) = treeview.get_model()[path]
        self.emit("application-activated", Application(name, pkgname))

    def _on_button_press_event(self, tree, event, col):
        if event.button != 1:
            return
        res = tree.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        if path is None:
            return
        # only act when the selection is already there
        selection = tree.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        yO = tree.get_cell_area(path, col).y
        for cx, cy, cw, ch, name in self.btn_regions:
            rect = gtk.gdk.Rectangle(cx, yO+cy, cw, ch)
            rr = gtk.gdk.region_rectangle(rect)

            if rr.point_in(x, y):
                appname, text, icon, overlay, pkgname, isactive = tree.get_model()[path]
                if name == 'info':
                    self.emit("application-activated", Application(appname, pkgname))
                elif name == 'install':
                    print (not overlay), 'install'
                break

    def _xy_is_over_focal_row(self, x, y):
        res = self.get_path_at_pos(x, y)
        cur = self.get_cursor()
        if not res:
            return False
        return self.get_path_at_pos(x, y)[0] == self.get_cursor()[0]


# XXX should we use a xapian.MatchDecider instead?
class AppViewFilter(object):
    """
    Filter that can be hooked into AppStore to filter for criteria that
    are based around the package details that are not listed in xapian
    (like installed_only) or archive section
    """
    def __init__(self, db, cache):
        self.db = db
        self.cache = cache
        self.supported_only = False
        self.installed_only = False
        self.not_installed_only = False
        self.only_packages_without_applications = False
    def set_supported_only(self, v):
        self.supported_only = v
    def set_installed_only(self, v):
        self.installed_only = v
    def set_not_installed_only(self, v):
        self.not_installed_only = v
    def get_supported_only(self):
        return self.supported_only
    def set_only_packages_without_applications(self, v):
        """
        only show packages that are not displayed as applications

        e.g. abiword (the package document) will not be displayed
             because there is a abiword application already
        """
        self.only_packages_without_applications = v
    def get_only_packages_without_applications(self, v):
        return self.only_packages_without_applications
    def filter(self, doc, pkgname):
        """return True if the package should be displayed"""
        #logging.debug("filter: supported_only: %s installed_only: %s '%s'" % (
        #        self.supported_only, self.installed_only, pkgname))
        if self.only_packages_without_applications:
            if not doc.get_value(XAPIAN_VALUE_PKGNAME):
                # "if not self.db.xapiandb.postlist("AP"+pkgname):"
                # does not work for some reason
                for m in self.db.xapiandb.postlist("AP"+pkgname):
                    return False
        if self.installed_only:
            if (not self.cache.has_key(pkgname) or
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
    (cache, db, view) = data
    query = get_query_from_search_entry(new_text)
    view.set_model(AppStore(cache, db, icons, query))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    xapian_base_path = XAPIAN_BASE_PATH
    pathname = os.path.join(xapian_base_path, "xapian")

    # the store
    cache = apt.Cache(apt.progress.OpTextProgress())
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the store
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(True)
    filter.set_installed_only(True)
    store = AppStore(cache, db, icons, sort=True, filter=filter)

    # test bisect based search
    import bisect
    print store.sorted
    index = bisect.bisect(store.apps, Application("Compiz","compiz"))
    print "index: ", index

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (cache, db, view))

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400, 400)
    win.show_all()


