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
import gettext
import glib
import gobject
import gtk
import locale
import logging
import math
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
from softwarecenter.backend import get_install_backend

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
     COL_INSTALLED,
     COL_AVAILABLE,
     COL_PKGNAME,
     COL_POPCON,
     COL_IS_ACTIVE,
     COL_ACTION_IN_PROGRESS,
     ) = range(9)

    column_type = (str,
                   str,
                   gtk.gdk.Pixbuf,
                   bool,
                   bool,
                   str,
                   int,
                   bool,
                   int)

    ICON_SIZE = 24
    MAX_STARS = 5

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
        # this is used to re-set the cursor
        self.app_index_map = {}
        # this is used to find the in-progress rows
        self.pkgname_index_map = {}
        self.sorted = sort
        self.filter = filter
        self.active = True
        self.backend = get_install_backend()
        self.backend.connect("transaction-progress-changed", self._on_transaction_progress_changed)
        # rowref of the active app and last active app
        self.active_app = None
        self._prev_active_app = 0
        self._searches_sort_mode = self._get_searches_sort_mode()
        if not search_query:
            # limit to applications
            for m in db.xapiandb.postlist("ATapplication"):
                doc = db.xapiandb.get_document(m.docid)
                if filter and self.is_filtered_out(filter, doc):
                    continue
                appname = doc.get_value(XAPIAN_VALUE_APPNAME)
                pkgname = db.get_pkgname(doc)
                popcon = db.get_popcon(doc)
                self.apps.append(Application(appname, pkgname, popcon))
            self.apps.sort()
            for (i, app) in enumerate(self.apps):
                self.app_index_map[app] = i
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
                app_index = 0
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
                    popcon = db.get_popcon(doc)
                    app = Application(appname, pkgname, popcon)
                    if not app in already_added:
                        self.apps.append(app)
                        already_added.add(app)
                        if not sort:
                            self.app_index_map[app] = app_index
                            app_index = app_index + 1
            if sort:
                self.apps.sort()
                for (i, app) in enumerate(self.apps):
                    self.app_index_map[app] = i
            # build the pkgname map
            for (i, app) in enumerate(self.apps):
                if not app.pkgname in self.pkgname_index_map:
                    self.pkgname_index_map[app.pkgname] = []
                self.pkgname_index_map[app.pkgname].append(i)

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
    def _set_active_app(self, path):
        """ helper that emits row_changed signals for the new
            and previous selected app
        """
        self.active_app = path
        self.row_changed(self._prev_active_app,
                         self.get_iter(self._prev_active_app))
        self._prev_active_app = path
        self.row_changed(path, self.get_iter(path))

    def _calc_normalized_rating(self, raw_rating):
        if raw_rating:
            r  = int(self.MAX_STARS * math.log(raw_rating)/math.log(self.db.popcon_max+1))
        else:
            r = 0
        return r

    def _on_transaction_progress_changed(self, backend, pkgname, progress):
        if (not self.apps or
            not self.active or
            not pkgname in self.pkgname_index_map):
            return
        for index in self.pkgname_index_map[pkgname]:
            row = self[index]
            self.row_changed(row.path, row.iter)
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
        try:
            app = self.apps[rowref]
        except IndexError:
            logging.exception("on_get_value: rowref=%s apps=%s" % (rowref, self.apps))
            return
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
        elif column == self.COL_INSTALLED:
            pkgname = app.pkgname
            if self.cache.has_key(pkgname) and self.cache[pkgname].isInstalled:
                return True
            return False
        elif column == self.COL_AVAILABLE:
            pkgname = app.pkgname
            return self.cache.has_key(pkgname)
        elif column == self.COL_PKGNAME:
            pkgname = app.pkgname
            return pkgname
        elif column == self.COL_POPCON:
            return self._calc_normalized_rating(self.apps[rowref].popcon)
        elif column == self.COL_IS_ACTIVE:
            return (rowref == self.active_app)
        elif column == self.COL_ACTION_IN_PROGRESS:
            if app.pkgname in self.backend.pending_transactions:
                return self.backend.pending_transactions[app.pkgname]
            else:
                return -1
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


class CellRendererButton:

    def __init__(self, layout, markup, alt_markup=None, xpad=20, ypad=6):
        if not alt_markup:
            w, h, mx, amx = self._calc_markup_params(layout, markup, xpad, ypad)
        else:
            w, h, mx, amx = self._calc_markup_params_alt(layout, markup, alt_markup, xpad, ypad)

        self.params = {
            'label': markup,
            'markup': markup,
            'alt_markup': alt_markup,
            'width': w,
            'height': h,
            'x_offset_const': 0,
            'y_offset_const': 0,
            'region_rect': gtk.gdk.region_rectangle(gtk.gdk.Rectangle(0,0,0,0)),
            'xpad': xpad,
            'ypad': ypad,
            'sensitive': True,
            'state': gtk.STATE_NORMAL,
            'layout_x': mx,
            'markup_x': mx,
            'alt_markup_x': amx
            }
        self.use_alt = False
        return

    def _calc_markup_params(self, layout, markup, xpad, ypad):
        layout.set_markup(markup)
        w = self._get_layout_pixel_width(layout) + 2*xpad
        h = self._get_layout_pixel_height(layout) + 2*ypad
        return w, h, xpad, 0

    def _calc_markup_params_alt(self, layout, markup, alt_markup, xpad, ypad):
        layout.set_markup(markup)
        mw = self._get_layout_pixel_width(layout)
        layout.set_markup(alt_markup)
        amw = self._get_layout_pixel_width(layout)

        if amw > mw:
            w = amw + 2*xpad
            mx = xpad + (amw - mw)/2
            amx = xpad
        else:
            w = mw + 2*xpad
            mx = xpad
            amx = xpad + (mw - amw)/2

        # assume text height is the same for markups.
        h = self._get_layout_pixel_height(layout) + 2*ypad
        return w, h, mx, amx

    def _get_layout_pixel_width(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[2]

    def _get_layout_pixel_height(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[3]

    def set_state(self, state):
        if self.params['sensitive']:
            self.params['state'] = state
        return

    def set_sensitive(self, is_sensitive):
        self.params['sensitive'] = is_sensitive
        if not is_sensitive:
            self.set_state(gtk.STATE_INSENSITIVE)
        else:
            self.set_state(gtk.STATE_NORMAL)
        return

    def set_use_alt_markup(self, use_alt):
        if self.use_alt == use_alt: 
            return
        self.use_alt = use_alt
        p = self.params
        if use_alt:
            p['label'] = p['alt_markup']
            p['layout_x'] = p['alt_markup_x']
        else:
            p['label'] = p['markup']
            p['layout_x'] = p['markup_x']
        return

    def get_use_alt_markup(self):
        return self.use_alt

    def set_param(self, key, value):
        self.params[key] = value
        return

    def get_param(self, key):
        return self.params[key]

    def get_params(self, *keys):
        r = []
        for k in keys:
            r.append(self.params[k])
        return r

    def draw(self, window, widget, layout, cell_xO, cell_yO):
        p = self.params
        xO, yO, w, h = self.get_params('x_offset_const', 'y_offset_const', 'width', 'height')
        state = p['state']
        layout.set_markup(p['label'])

        dst_x = xO+cell_xO
        dst_y = yO+cell_yO

        # backgound "button" rect
        widget.style.paint_box(window,
                               state,
                               gtk.SHADOW_OUT,
                               (dst_x, dst_y, w, h),
                               widget,
                               "button",
                               dst_x,
                               dst_y,
                               w,
                               h)

        # cache region_rectangle for event checks
        p['region_rect'] = gtk.gdk.region_rectangle(gtk.gdk.Rectangle(dst_x, dst_y, w, h))

        # label stuff
        dst_x += p['layout_x']
        dst_y += p['ypad']

#        # if btn_has_focus:
#        # draw focal rect
#        widget.style.paint_focus(window,
#                                 state,
#                                 (dst_x, dst_y, w, h),
#                                 widget,
#                                 "button",
#                                 dst_x-2,       # x
#                                 dst_y-2,       # y
#                                 w-4,          # width
#                                 h-4)          # height

        # draw Install button label
        widget.style.paint_layout(window,
                            state,
                            True,
                            (dst_x, dst_y, w, h),
                            widget,
                            None,
                            dst_x,
                            dst_y,
                            layout)
        return


# custom cell renderer to support dynamic grow
class CellRendererAppView(gtk.GenericCellRenderer):

    __gproperties__ = {
        'markup': (gobject.TYPE_STRING, 'Markup', 'Pango markup', '',
                    gobject.PARAM_READWRITE),

#        'addons': (bool, 'AddOns', 'Has add-ons?', False,
#                   gobject.PARAM_READWRITE),

        # numbers mean: min: 0, max: 5, default: 0
        'rating': (gobject.TYPE_INT, 'Rating', 'Popcon rating', 0, 5, 0,
            gobject.PARAM_READWRITE),

#        'reviews': (gobject.TYPE_INT, 'Reviews', 'Number of reviews', 0, 100, 0,
#            gobject.PARAM_READWRITE),

        'isactive': (bool, 'IsActive', 'Is active?', False,
                    gobject.PARAM_READWRITE),

        'installed': (bool, 'installed', 'Is the app installed', False,
                     gobject.PARAM_READWRITE),

        'available': (bool, 'available', 'Is the app available for install', False,
                     gobject.PARAM_READWRITE),

        'action_in_progress': (gobject.TYPE_INT, 'Action Progress', 'Action progress', -1, 100, -1,
                     gobject.PARAM_READWRITE),
        }

    # class constants
    DEFAULT_HEIGHT = 38
    BUTTON_HEIGHT = 32

    def __init__(self, show_ratings):
        self.__gobject_init__()
        self.markup = None
        self.rating = 0
        self.reviews = 0
        self.isactive = False
        self.installed = False
        self.show_ratings = show_ratings
        # get rating icons
        icons = gtk.icon_theme_get_default()
        self.star_pixbuf = icons.load_icon("sc-emblem-favorite", 16, 0)
        self.star_not_pixbuf = icons.load_icon("sc-emblem-favorite-not", 16, 0)
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)

    def do_get_property(self, pspec):
        return getattr(self, pspec.name)

    def _get_layout_pixel_width(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[2]

    def _get_layout_pixel_height(self, layout):
        (logical_extends, ink_extends) = layout.get_pixel_extents()
        # extens is (x, y, width, height)
        return ink_extends[3]

    def draw_appname_summary(self, window, widget, cell_area, layout, xpad, ypad, flags):
        # work out where to draw layout
        dst_x = cell_area.x + xpad
        dst_y = cell_area.y + ypad

        w = self.star_pixbuf.get_width()
        h = self.star_pixbuf.get_height()
        max_star_width = AppStore.MAX_STARS*(w+1) + xpad

        # work out layouts max width
        lw = self._get_layout_pixel_width(layout)
        if lw >= cell_area.width-cell_area.y-2*xpad - max_star_width:
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

    def draw_rating_and_reviews(self, window, widget, cell_area, layout, xpad, ypad, w, h, flags):
        # draw star rating
        dst_x = cell_area.width-xpad
        dst_y = 1+ypad
        tw = self.draw_rating(window, cell_area, dst_x, dst_y, self.rating)

        # draw number of reviews
        nr_reviews_str = gettext.ngettext("%s review",
                                          "%s reviews",
                                          self.reviews) % self.reviews
        layout.set_markup("<small>%s</small>" % nr_reviews_str)
        lw = self._get_layout_pixel_width(layout)
        dst_x -= tw - 32 - (tw-lw)/2

        widget.style.paint_layout(window,
                                  flags,
                                  True,
                                  cell_area,
                                  widget,
                                  None,
                                  dst_x,
                                  cell_area.y+ypad+h+1,
                                  layout)
        return

    def draw_rating(self, window, cell_area, dst_x, dst_y, r):
        w = self.star_pixbuf.get_width()
        tw = AppStore.MAX_STARS*(w+1)    # total 5star width + 1 px spacing per star
        for i in range(AppStore.MAX_STARS):
            if i < r:
                window.draw_pixbuf(None,
                                   self.star_pixbuf,                    # icon
                                   0, 0,                                # src pixbuf
                                   dst_x - tw + i*(w+1) + 32,           # xdest
                                   cell_area.y + dst_y,                 # ydest
                                   -1, -1,                              # size
                                   0, 0, 0)                             # dither
            else:
                window.draw_pixbuf(None,
                                   self.star_not_pixbuf,                # icon
                                   0, 0,                                # src pixbuf
                                   dst_x - tw + i*(w+1) + 32,   # xdest
                                   cell_area.y + dst_y,                 # ydest
                                   -1, -1,                              # size
                                   0, 0, 0)                             # dither
        return tw

    def draw_progress(self, window, widget, cell_area, layout, ypad, flags):
        percent = self.props.action_in_progress
        w, xO = widget.buttons["action"].get_params('width', 'x_offset_const')
        dst_x = cell_area.width + xO
        dst_y = cell_area.y + ypad + 1
        h = self.star_pixbuf.get_height()

        # progress trough
        widget.style.paint_box(window, gtk.STATE_NORMAL, gtk.SHADOW_IN,
                               (dst_x, dst_y, w, h),
                               widget, 
                               "progressbar",
                               dst_x,
                               dst_y,
                               w,
                               h)
        dst_x += 2
        dst_y += 2
        w -= 4
        h -= 4

        # progress fill
        widget.style.paint_box(window, gtk.STATE_SELECTED, gtk.SHADOW_NONE,
                               (dst_x, dst_y, (float(percent)/w)*100, h),
                               widget, 
                               "progressbar",
                               dst_x,
                               dst_y,
                               w,
                               h)

        # Working... note
        layout.set_markup("<small>%s</small>" % _("Working..."))
        lw = self._get_layout_pixel_width(layout)
        dst_x += (2 + (w-lw)/2)
        dst_y += (ypad+h+1)
        widget.style.paint_layout(window,
                                  flags,
                                  True,
                                  (dst_x, dst_y, lw, self._get_layout_pixel_height(layout)),
                                  widget,
                                  None,
                                  dst_x,
                                  dst_y,
                                  layout)

    def on_render(self, window, widget, background_area, cell_area,
                  expose_area, flags):
        xpad = self.get_property('xpad')
        ypad = self.get_property('ypad')

        # create pango layout with markup
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.markup)
        layout.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        w, h = self.draw_appname_summary(window, widget, cell_area, layout, xpad, ypad, flags)

        if not self.isactive:
            if self.show_ratings:
                # draw star rating only
                dst_x = cell_area.width-xpad
                dst_y = (cell_area.height-h)/2
                self.draw_rating(window, cell_area, dst_x, dst_y, self.rating)
            return

        # Install/Remove button
        # only draw a install/remove button if the app is actually available
        if self.available:
            btn = widget.buttons['action']
            if self.installed:
                btn.set_use_alt_markup(True)
            else:
                btn.set_use_alt_markup(False)
            btn.draw(window, widget, layout, cell_area.width, cell_area.y)
            # check if the current app has a action that is in progress
            if self.props.action_in_progress < 0:
                # draw buttons and rating with the number of reviews
                self.draw_rating_and_reviews(window, widget, cell_area, layout, xpad, ypad, w, h, flags)
            else:
                self.draw_progress(window, widget, cell_area, layout, ypad, flags)

        # More Info button
        btn = widget.buttons['info']
        btn.draw(window, widget, layout, cell_area.x, cell_area.y)
        return

    def on_get_size(self, widget, cell_area):
        h = self.DEFAULT_HEIGHT
        if self.isactive:
            h += self.BUTTON_HEIGHT
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
        # always render icon app icon centered with respect to an unexpanded CellRendererAppView
        area = (cell_area.x+(cell_area.width-AppStore.ICON_SIZE)/2,
                cell_area.y+(CellRendererAppView.DEFAULT_HEIGHT-AppStore.ICON_SIZE)/2,
                AppStore.ICON_SIZE,
                AppStore.ICON_SIZE)

        gtk.CellRendererPixbuf.do_render(self, window, widget, background_area,
                                         area, area, flags)
        overlay = self.overlay
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
        "application-request-action" : (gobject.SIGNAL_RUN_LAST,
                                        gobject.TYPE_NONE,
                                        (gobject.TYPE_PYOBJECT, str),
                                       ),
    }

    def __init__(self, show_ratings, store=None):
        gtk.TreeView.__init__(self)
        self.buttons = {}
        self.focal_btn = None

        # FIXME: mvo this makes everything sluggish but its the only
        #        way to make the rows grow (sluggish because gtk will
        #        use a lot of the handlers to validate the treeview)
        #self.set_fixed_height_mode(True)
        self.set_headers_visible(False)
        tp = CellRendererPixbufWithOverlay("software-center-installed")
        column = gtk.TreeViewColumn("Icon", tp,
                                    pixbuf=AppStore.COL_ICON,
                                    overlay=AppStore.COL_INSTALLED)
        column.set_fixed_width(32)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        self.append_column(column)

        tr = CellRendererAppView(show_ratings)
        tr.set_property('xpad', 3)
        tr.set_property('ypad', 2)

        column = gtk.TreeViewColumn("Apps", tr, 
                                    markup=AppStore.COL_TEXT,
                                    rating=AppStore.COL_POPCON,
                                    isactive=AppStore.COL_IS_ACTIVE,
                                    installed=AppStore.COL_INSTALLED, 
                                    available=AppStore.COL_AVAILABLE,
                                    action_in_progress=AppStore.COL_ACTION_IN_PROGRESS)
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
        self.connect("realize", self._on_realize, tr)
        self.connect("button-press-event", self._on_button_press_event, column)
        self.connect("cursor-changed", self._on_cursor_changed)
        self.connect("motion-notify-event", self._on_motion, tr, column)

    def _on_realize(self, widget, tr, xpad=3, ypad=2):
        pc = widget.get_pango_context()
        layout = pango.Layout(pc)

        action_btn = CellRendererButton(layout, markup=_("Install"), alt_markup=_("Remove"))
        info_btn = CellRendererButton(layout, _("More Info"))

        # set offset constants
        yO = tr.DEFAULT_HEIGHT+(tr.BUTTON_HEIGHT-action_btn.get_param('height'))/2
        action_btn.set_param('x_offset_const', 32 - xpad - action_btn.get_param('width'))
        action_btn.set_param('y_offset_const', yO)

        info_btn.set_param('x_offset_const', xpad)
        info_btn.set_param('y_offset_const', yO)

        self.buttons['action'] = action_btn
        self.buttons['info'] = info_btn

    def _on_motion(self, tree, event, tr, col):
        x, y = int(event.x), int(event.y)
        if not self._xy_is_over_focal_row(x, y) or not self.buttons:
            self.window.set_cursor(None)
            return

        path = tree.get_path_at_pos(x, y)
        if not path: return

        for id, btn in self.buttons.iteritems():
            rr = btn.get_param('region_rect')
            if rr.point_in(x, y) and btn.get_param('sensitive'):
                if id != self.focal_btn:
                    self.focal_btn = id
                    btn.set_state(gtk.STATE_PRELIGHT)
                    store = tree.get_model()
                    store.row_changed(path[0], store.get_iter(path[0]))
                self.window.set_cursor(self._cursor_hand)
                break
            elif btn.get_param('sensitive'):
                self.focal_btn = None
                btn.set_state(gtk.STATE_NORMAL)
                store = tree.get_model()
                store.row_changed(path[0], store.get_iter(path[0]))
                self.window.set_cursor(None)
        return

    def _on_cursor_changed(self, view):
        model = view.get_model()
        selection = view.get_selection()
        (model, it) = selection.get_selected()
        if it is None:
            return
        # update active app, use row-ref as argument
        model._set_active_app(model.get_path(it)[0])
        # emit selected signal
        name = model[it][AppStore.COL_APP_NAME]
        pkgname = model[it][AppStore.COL_PKGNAME]
        popcon = model[it][AppStore.COL_POPCON]
        self.emit("application-selected", Application(name, pkgname, popcon))
        return

    def _on_row_activated(self, view, path, column):
        model = view.get_model()
        name = model[path][AppStore.COL_APP_NAME]
        pkgname = model[path][AppStore.COL_PKGNAME]
        popcon = model[path][AppStore.COL_POPCON]
        self.emit("application-activated", Application(name, pkgname, popcon))

    def _on_button_press_event(self, view, event, col):
        if event.button != 1:
            return
        res = view.get_path_at_pos(int(event.x), int(event.y))
        if not res:
            return
        (path, column, wx, wy) = res
        if path is None:
            return
        # only act when the selection is already there
        selection = view.get_selection()
        if not selection.path_is_selected(path):
            return

        x, y = int(event.x), int(event.y)
        yO = view.get_cell_area(path, col).y
        for btn_id, btn in self.buttons.iteritems():
            rr = btn.get_param('region_rect')
            if rr.point_in(x, y) and btn.get_param('sensitive'):
                self.focal_btn = btn_id
                btn.set_state(gtk.STATE_ACTIVE)

                model = view.get_model()
                appname = model[path][AppStore.COL_APP_NAME]
                pkgname = model[path][AppStore.COL_PKGNAME]
                installed = model[path][AppStore.COL_INSTALLED]
                popcon = model[path][AppStore.COL_POPCON]

                gobject.timeout_add(100,
                                    self._app_activated_cb,
                                    path,
                                    btn,
                                    btn_id,
                                    appname,
                                    pkgname,
                                    popcon,
                                    installed,)
                break

    def _app_activated_cb(self, path, btn, btn_id, appname, pkgname, popcon, installed):
        if btn_id == 'info':
            btn.set_state(gtk.STATE_NORMAL)
            self.emit("application-activated", Application(appname, pkgname, popcon))
        elif btn_id == 'action':
            if installed:
                perform_action = "remove"
            else:
                perform_action = "install"
            self.emit("application-request-action", Application(appname, pkgname, popcon), perform_action)
        return False

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
    icons.prepend_search_path("/usr/share/app-install/icons/")
    icons.prepend_search_path("/usr/share/software-center/icons/")

    # now the store
    filter = AppViewFilter(db, cache)
    filter.set_supported_only(False)
    filter.set_installed_only(False)
    store = AppStore(cache, db, icons, sort=True, filter=filter)

    # gui
    scroll = gtk.ScrolledWindow()
    view = AppView(store)

    entry = gtk.Entry()
    entry.connect("changed", on_entry_changed, (cache, db, view))
    entry.set_text("f")

    box = gtk.VBox()
    box.pack_start(entry, expand=False)
    box.pack_start(scroll)

    win = gtk.Window()
    scroll.add(view)
    win.add(box)
    win.set_size_request(400, 400)
    win.show_all()

    gtk.main()

