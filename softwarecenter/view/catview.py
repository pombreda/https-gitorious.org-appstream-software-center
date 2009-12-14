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
import gobject
import gtk
import logging
import os
import xapian

from widgets.wkwidget import WebkitWidget

from gettext import gettext as _
from xml.etree import ElementTree as ET
from ConfigParser import ConfigParser

(COL_CAT_NAME,
 COL_CAT_PIXBUF,
 COL_CAT_QUERY,
 COL_CAT_MARKUP) = range(4)

def encode_for_xml(unicode_data, encoding="ascii"):
    return unicode_data.encode(encoding, 'xmlcharrefreplace')

class Category(object):
    """represents a menu category"""
    def __init__(self, untranslated_name, name, iconname, query, subcategories):
        self.name = name
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        self.query = query
        self.subcategories = subcategories

class CategoriesView(WebkitWidget):

    CATEGORY_ICON_SIZE = 48

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (str, gobject.TYPE_PYOBJECT),
                              )
        }

    def __init__(self, datadir, desktopdir, db, icons, root_category=None):
        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        db - a Database object
        icons - a gtk.IconTheme
        root_category - a Category class with subcategories or None
        """
        super(CategoriesView, self).__init__(datadir)
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))
        self.icons = icons
        if not root_category:
            self.header = _("Departments")
            self.categories = self.parse_applications_menu(desktopdir)
        else:
            self.header = root_category.name
            self.categories = root_category.subcategories
        self.connect("load-finished", self._on_load_finished)

    def on_category_clicked(self, name):
        """emit the category-selected signal when a category was clicked"""
        logging.debug("on_category_changed: %s" % name)
        for n in self.categories:
            if n.name == name:
                self.emit("category-selected", name, n.query)

    # run javascript inside the html
    def _on_load_finished(self, view, frame):
        """
        helper for the webkit widget that injects the categories into
        the page when it has finished loading
        """
        for cat in sorted(self.categories, cmp=self._cat_sort_cmp):
            iconpath = ""
            iconinfo = self.icons.lookup_icon(cat.iconname, 
                                              self.CATEGORY_ICON_SIZE, 0)
            if iconinfo:
                iconpath = iconinfo.get_filename()
                logging.debug("icon: %s %s" % (iconinfo, iconpath))
            # FIXME: this looks funny with german locales
            s = 'addCategory("%s","%s")' % (cat.name, iconpath)
            logging.debug("running script '%s'" % s)
            self.execute_script(s)

    # substitute stuff
    def wksub_icon_size(self):
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

    # helper code for menu parsing etc
    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "Packages":
            return 1
        elif b.untranslated_name == "Packages":
            return -1
        if a.untranslated_name == "Other":
            return 1
        elif b.untranslated_name == "Other":
            return -1
        elif a.untranslated_name == "Programming":
            return 1
        elif b.untranslated_name == "Programming":
            return -1
        return cmp(a.name, b.name)

    def _parse_directory_tag(self, element):
        cp = ConfigParser()
        fname = "/usr/share/desktop-directories/%s" % element.text
        logging.debug("reading '%s'" % fname)
        cp.read(fname)
        try:
            untranslated_name = name = cp.get("Desktop Entry","Name")
        except Exception, e:
            logging.warn("'%s' has no name" % fname)
            return None
        try:
            gettext_domain = cp.get("Desktop Entry", "X-Ubuntu-Gettext-Domain")
        except:
            gettext_domain = None
        try:
            icon = cp.get("Desktop Entry","Icon")
        except Exception, e:
            icon = "applications-other"
            if gettext_domain:
                name = gettext.dgettext(gettext_domain, untranslated_name)
        return (untranslated_name, name, gettext_domain, icon)

    def _parse_include_tag(self, element):
        query = xapian.Query("")
        for include in element.getchildren():
            if include.tag == "And":
                for and_elem in include.getchildren():
                    if and_elem.tag == "Not":
                        for not_elem in and_elem.getchildren():
                            if not_elem.tag == "Category":
                                q = xapian.Query("AC"+not_elem.text.lower())
                                query = xapian.Query(xapian.Query.OP_AND_NOT, query, q)
                                                
                    elif and_elem.tag == "Category":
                        logging.debug("adding: %s" % and_elem.text)
                        q = xapian.Query("AC"+and_elem.text.lower())
                        query = xapian.Query(xapian.Query.OP_AND, query, q)
                    else: 
                        print "UNHANDLED: ", and_elem.tag, and_elem.text
            # without "and" tag we take the first entry
            elif include.tag == "Category":
                return xapian.Query("AC"+include.text.lower())
            else:
                logging.warn("UNHANDLED: _parse_include_tag: %s" % include.tag)
        return query

    def _parse_menu_tag(self, item, only_unallocated):
        name = None
        untranslated_name = None
        query = None
        icon = None
        subcategories = []
        for element in item.getchildren():
            if element.tag == "Name":
                name = element.text
            elif element.tag == "Directory":
                (untranslated_name, name, gettext_domain, icon) = self._parse_directory_tag(element)
            elif element.tag == "Include":
                query = self._parse_include_tag(element)
            elif element.tag == "OnlyUnallocated":
                 only_unallocated.add(untranslated_name)
            elif element.tag == "Menu":
                subcat = self._parse_menu_tag(element, only_unallocated)
                if subcat:
                    subcategories.append(subcat)
            else:
                print "UNHANDLED tag in _parse_menu_tag: ", element.tag
                
        if untranslated_name and query:
            return Category(untranslated_name, name, icon, query, subcategories)
        return None

    def parse_applications_menu(self, datadir):
        " parse a application menu and return a list of Category objects"""
        tree = ET.parse(datadir+"/desktop/applications.menu")
        categories = {}
        only_unallocated = set()
        root = tree.getroot()
        for child in root.getchildren():
            category = None
            if child.tag == "Menu":
                category = self._parse_menu_tag(child, only_unallocated)
            if category:
                categories[category.untranslated_name] = category

        # post processing for <OnlyUnallocated>
        for unalloc in only_unallocated:
            if not unalloc in categories:
                logging.debug("not category '%s' in the unalloced ones" % unalloc)
                continue
            cat_unalloc = categories[unalloc]
            for key in categories:
                if key != unalloc:
                    cat = categories[key]
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT, cat_unalloc.query, cat.query)
            categories[unalloc] = cat_unalloc

        # add packages
        query = xapian.Query(xapian.Query.OP_AND_NOT, xapian.Query(""), xapian.Query("ATapplication"))
        pkg_category = Category("Packages", _("System Packages"), "applications-other", query, [])
        categories["Packages"] = pkg_category
            
        # debug print
        for catname in categories:
            cat = categories[catname]
            logging.debug("%s %s %s" % (cat.name, cat.iconname, cat.query.get_description()))
        return categories.values()
        
    def _get_pango_font_description(self):
        return gtk.Label("pango").get_pango_context().get_font_description()
        
    def _get_font_description_property(self, property):
        description = self._get_pango_font_description()
        return getattr(description, "get_%s" % property)()




# test code
def category_activated(iconview, name, query, db):
    #(name, pixbuf, query) = iconview.get_model()[path]
    enquire = xapian.Enquire(db)
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
    from softwarecenter.enums import *
    #logging.basicConfig(level=logging.DEBUG)

    appdir = "/usr/share/app-install"
    datadir = "./data"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

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
