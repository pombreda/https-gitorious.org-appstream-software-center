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
    def __init__(self, untranslated_name, name, iconname, query):
        self.name = name
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        self.query = query


class CategoriesView(WebkitWidget):

    CATEGORY_ICON_SIZE = 48

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (str, gobject.TYPE_PYOBJECT),
                              )
        }

    def __init__(self, datadir, desktopdir, xapiandb, icons):
        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        xapiandb - a xapian.Database object
        icons - a gtk.IconTheme
        """
        super(CategoriesView, self).__init__(datadir)
        self.icons = icons
        self.categories = self.parse_applications_menu(desktopdir)
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
        return _("Departments")

    # helper code for menu parsing etc
    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "Other":
            return 1
        elif b.untranslated_name == "Other":
            return -1
        elif a.untranslated_name == "Programming":
            return 1
        elif b.untranslated_name == "Programming":
            return -1
        return cmp(a.name, b.name)

    def parse_applications_menu(self, datadir):
        " parse a application menu and return a list of Category objects"""
        tree = ET.parse(datadir+"/desktop/applications.menu")
        categories = {}
        only_unallocated = set()
        root = tree.getroot()
        for child in root.getchildren():
            if child.tag == "Menu":
                name = None
                untranslated_name = None
                query = None
                icon = None
                for element in child.getchildren():
                    if element.tag == "Name":
                        name = element.text
                    elif element.tag == "Directory":
                        cp = ConfigParser()
                        cp.read("/usr/share/desktop-directories/%s" % element.text)
                        try:
                            gettext_domain = cp.get("Desktop Entry", "X-Ubuntu-Gettext-Domain")
                        except:
                            gettext_domain = None
                        icon = cp.get("Desktop Entry","Icon")
                        untranslated_name = cp.get("Desktop Entry","Name")
                        if gettext_domain:
                            name = gettext.dgettext(gettext_domain, untranslated_name)
                    elif element.tag == "Include":
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
                    elif element.tag == "OnlyUnallocated":
                        only_unallocated.add(untranslated_name)
                    if untranslated_name and query:
                        categories[untranslated_name] = Category(untranslated_name, name, icon, query)
        # post processing for <OnlyUnallocated>
        for unalloc in only_unallocated:
            cat_unalloc = categories[unalloc]
            for key in categories:
                if key != unalloc:
                    cat = categories[key]
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT, cat_unalloc.query, cat.query)
            categories[unalloc] = cat_unalloc
        # debug print
        for catname in categories:
            cat = categories[catname]
            logging.debug("%s %s %s" % (cat.name, cat.iconname, cat.query.get_description()))
        return categories.values()
        




# test code
def category_activated(iconview, name, query, xapiandb):
    #(name, pixbuf, query) = iconview.get_model()[path]
    enquire = xapian.Enquire(xapiandb)
    enquire.set_query(query)
    matches = enquire.get_mset(0, 2000)
    for m in matches:
        doc = m[xapian.MSET_DOCUMENT]
        appname = doc.get_data()
        print "appname: ", appname,
            #for t in doc.termlist():
            #    print "'%s': %s (%s); " % (t.term, t.wdf, t.termfreq),
            #print "\n"
    print len(matches)

if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    appdir = "/usr/share/app-install"
    datadir = "./data"

    xapian_base_path = "/var/cache/software-store"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the store
    view = CategoriesView(datadir, appdir, db, icons)
    #view = CategoriesView(datadir, db, icons)
    view.connect("category-selected", category_activated, db)

    # gui
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    win = gtk.Window()
    win.add(scroll)
    view.grab_focus()
    win.set_size_request(500,200)
    win.show_all()

    gtk.main()
