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

import gettext
import glib
import glob
import gobject
import gtk
import locale
import logging
import os
import xapian


from ConfigParser import ConfigParser
from gettext import gettext as _
from widgets.wkwidget import WebkitWidget
from xml.etree import ElementTree as ET

from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.utils import *
from softwarecenter.distro import get_distro

from catview import *

class CategoriesViewWebkit(WebkitWidget, CategoriesView):

    CATEGORY_ICON_SIZE = 64
    SUB_CATEGORY_ICON_SIZE = 48

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (gobject.TYPE_PYOBJECT, ),
                              ),
        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
        }

    def __init__(self, datadir, desktopdir, cache, db, icons, apps_filter, root_category=None):
        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        cache - a apt cache
        db - a Database object
        icons - a gtk.IconTheme
        root_category - a Category class with subcategories or None
        """
        WebkitWidget.__init__(self, datadir)
        CategoriesView.__init__(self)

        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))
        self.categories = []
        self.header = ""
        self.db = db
        self.cache = cache
        self.apps_filter = apps_filter
        self.icons = icons

        # FIXME: move this to shared code
        if not root_category:
            self.header = _("Departments")
            self.categories = self.parse_applications_menu(desktopdir)
            self.in_subsection = False
        else:
            self.in_subsection = True
            self.set_subcategory(root_category)
        self.connect("load-finished", self._on_load_finished)

    def set_subcategory(self, root_category, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name
        self.categories = root_category.subcategories
        self.refresh_html()
        # wait until html is ready
        while gtk.events_pending():
            gtk.main_iteration()

    def on_category_clicked(self, name):
        """emit the category-selected signal when a category was clicked"""
        logging.debug("on_category_changed: %s" % name)
        for cat in self.categories:
            if cat.name == name:
                self.emit("category-selected", cat)

    # run javascript inside the html
    def _on_load_finished(self, view, frame):
        """
        helper for the webkit widget that injects the categories into
        the page when it has finished loading
        """
        self._show_hide_header()
        self.add_all_categories()

    def _show_hide_header(self):
        if self.in_subsection:
            self.execute_script("hide_header();")
        else:
            self.execute_script("show_header();")

    def add_all_categories(self):
        """ add all categories to the view """
        for cat in sorted(self.categories, cmp=self._cat_sort_cmp):
            iconpath = ""
            if cat.iconname:
                if self.in_subsection:
                    size = self.SUB_CATEGORY_ICON_SIZE
                else:
                    size = self.CATEGORY_ICON_SIZE
                iconinfo = self.icons.lookup_icon(cat.iconname, size, 0)
                if iconinfo:
                    iconpath = iconinfo.get_filename()
                    logging.debug("icon: %s %s" % (iconinfo, iconpath))
                self.add_category(cat, iconpath)

    def add_category(self, cat, iconpath):
        """ add a single category """
        s = 'addCategory("%s","%s", "%s")' % (cat.name, 
                                              cat.untranslated_name,
                                              iconpath)
        logging.debug("running script '%s'" % s)
        self.execute_script(s)

    # substitute stuff
    def wksub_ubuntu_software_center(self):
        return get_distro().get_app_name()
    def wksub_icon_size(self):
        if self.in_subsection:
            return self.SUB_CATEGORY_ICON_SIZE
        else:
            return self.CATEGORY_ICON_SIZE
    def wksub_header(self):
        return self.header
    def wksub_text_direction(self):
        direction = gtk.widget_get_default_direction()
        if direction ==  gtk.TEXT_DIR_RTL:
            return 'DIR="RTL"'
        elif direction ==  gtk.TEXT_DIR_LTR:
            return 'DIR="LTR"'
    def wksub_font_family(self):
        return self._get_font_description_property("family")
        
    def wksub_font_weight(self):
        try:
            return self._get_font_description_property("weight").real
        except AttributeError:
            return int(self._get_font_description_property("weight"))
             
    def wksub_font_style(self):
        return self._get_font_description_property("style").value_nick
    def wksub_font_size(self):
        return self._get_font_description_property("size")/1024

    def wksub_featured_applications_image(self):
        return self._image_path("featured_applications_background")
    def wksub_button_background_left(self):
        return self._image_path("button_background_left")
    def wksub_button_background_right(self):
        return self._image_path("button_background_right")
    def wksub_heading_background_image(self):
        return self._image_path("heading_background_image")
    def wksub_basket_image(self):
        return self._image_path("basket")
    def wksub_arrow_image(self):
        return self._image_path("arrow")
    

    # helper code for menu parsing etc
    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name)) 

    def _get_pango_font_description(self):
        return gtk.Label("pango").get_pango_context().get_font_description()
        
    def _get_font_description_property(self, property):
        description = self._get_pango_font_description()
        return getattr(description, "get_%s" % property)()




# test code
def category_activated(iconview, category, db):
    #(name, pixbuf, query) = iconview.get_model()[path]
    name = category.name
    query = category.query
    enquire = xapian.Enquire(db.xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, 2000)
    for m in matches:
        doc = m[xapian.MSET_DOCUMENT]
        appname = doc.get_value(XAPIAN_VALUE_APPNAME)
        print "appname: ", appname,
            #for t in doc.termlist():
            #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
            #print "\n"
    print len(matches)

if __name__ == "__main__":
    import apt
    from softwarecenter.enums import *
    from softwarecenter.db.database import StoreDatabase
    logging.basicConfig(level=logging.DEBUG)

    appdir = "/usr/share/app-install"
    datadir = "./data"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    cache = apt.Cache()
    db = StoreDatabase(pathname, cache)
    db.open()

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the category view
    view = CategoriesView(datadir, appdir, db, icons)
    view.connect("category-selected", category_activated, db)
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    # now a sub-category view
    for cat in view.categories:
        if cat.untranslated_name == "Games":
            games_category = cat
    subview = CategoriesView(datadir, appdir, db, icons, games_category)
    subview.connect("category-selected", category_activated, db)
    scroll2 = gtk.ScrolledWindow()
    scroll2.add(subview)

    # pack and show
    vbox = gtk.VBox()
    vbox.pack_start(scroll, padding=6)
    vbox.pack_start(scroll2, padding=6)

    win = gtk.Window()
    win.add(vbox)
    view.grab_focus()
    win.set_size_request(700,600)
    win.show_all()

    gtk.main()
