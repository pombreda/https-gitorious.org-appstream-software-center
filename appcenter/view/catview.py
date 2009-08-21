# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
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

import gobject
import gtk
import logging
import os
import xapian


from gettext import gettext as _
from xml.etree import ElementTree as ET
from ConfigParser import ConfigParser

(COL_CAT_NAME,
 COL_CAT_PIXBUF,
 COL_CAT_QUERY) = range(3)

class CategoriesModel(gtk.ListStore):
    def __init__(self, desktopdir, xapiandb, icons):
        gtk.ListStore.__init__(self, str, gtk.gdk.Pixbuf, object)
        cat = self.parse_applications_menu(desktopdir)
        for key in sorted(cat.keys()):
            (iconname, query) = cat[key]
            icon = icons.load_icon(iconname, 24, 0)
            self.append([gobject.markup_escape_text(key), icon, query])

    def parse_applications_menu(self, datadir):
        " parse a application menu and build xapian querries from it "
        tree = ET.parse(datadir+"/desktop/applications.menu")
        categories = {}
        only_unallocated = set()
        root = tree.getroot()
        for child in root.getchildren():
            if child.tag == "Menu":
                name = None
                query = None
                icon = None
                for element in child.getchildren():
                    if element.tag == "Name":
                        name = element.text
                    elif element.tag == "Directory":
                        cp = ConfigParser()
                        cp.read("/usr/share/desktop-directories/%s" % element.text)
                        icon = cp.get("Desktop Entry","Icon")
                        name = cp.get("Desktop Entry","Name")
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
                                        print "adding: ", and_elem.text
                                        q = xapian.Query("AC"+and_elem.text.lower())
                                        query = xapian.Query(xapian.Query.OP_AND, query, q)
                                    else: 
                                        print "UNHANDLED: ", and_elem.tag, and_elem.text
                    elif element.tag == "OnlyUnallocated":
                        only_unallocated.add(name)
                    if name and query:
                        categories[name] = (icon, query)
        # post processing for <OnlyUnallocated>
        for unalloc in only_unallocated:
            (icon, query) = categories[unalloc]
            for key in categories:
                if key != unalloc:
                    (ic, q) = categories[key]
                    query = xapian.Query(xapian.Query.OP_AND_NOT, query, q)
            categories[unalloc] = (icon, query)
        # debug print
        for cat in categories:
            (icon, query) = categories[cat]
            print cat, query.get_description()
        return categories

class LabeledCategoriesView(gtk.Viewport):
    def __init__(self, datadir, xapiandb, icons):
        gtk.Viewport.__init__(self)
        # a vbox in the outside and a hbox in the inside
        vbox = gtk.VBox()
        align = gtk.Alignment()
        top = bottom = 2
        left = right = 8
        align.set_padding(top, bottom, left, right)
        # we need a eventbox around the label to set the background
        label = gtk.Label("")
        label.set_markup("<b>%s</b>" % _("Categories"))
        label.set_alignment(0.0, 0.5)
        align.add(label)
        align.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("yellow"))
        eb = gtk.EventBox()
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("yellow"))
        eb.add(align)
        # needed to make the background not spawn all over
        hbox_inside = gtk.HBox()
        hbox_inside.pack_start(eb, expand=False, fill=False)
        # FIXME: how to make sure the background color is right
        #hbox_inside.pack_start(gtk.IconView())
        vbox.pack_start(hbox_inside, expand=False, fill=False)
        # and now the categoryies
        self.catview = CategoriesView(datadir, xapiandb, icons)
        vbox.pack_start(self.catview)
        self.add(vbox)
        # FIXME: add the row-activated signal

class CategoriesView(gtk.IconView):
    def __init__(self, datadir, xapiandb, icons):
        # model
        model = CategoriesModel(datadir, xapiandb, icons)
        gtk.IconView.__init__(self, model)
        # data
        self.xapiandb = xapiandb
        self.icons = icons
        self.cursor_hand = gtk.gdk.Cursor(gtk.gdk.HAND2)
        # customization
        self.set_markup_column(COL_CAT_NAME)
        self.set_pixbuf_column(COL_CAT_PIXBUF)
        # signals
        self.connect("motion-notify-event", self.on_motion_notify_event)
        self.connect("button-press-event", self.on_button_press_event)
    def on_motion_notify_event(self, widget, event):
        #print "on_motion_notify_event: ", event
        path = self.get_path_at_pos(event.x, event.y)
        if path is None:
            self.window.set_cursor(None)
        else:
            self.window.set_cursor(self.cursor_hand)
    def on_button_press_event(self, widget, event):
        #print "on_button_press_event: ", event
        path = self.get_path_at_pos(event.x, event.y)
        if event.button != 1 or path is None:
            return
        self.emit("item-activated", path)

# test code
def category_activated(iconview, path, xapiandb):
    (name, pixbuf, query) = iconview.get_model()[path]
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

    datadir = "/usr/share/app-install"

    xapian_base_path = "/var/cache/app-install"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = xapian.Database(pathname)

    # additional icons come from app-install-data
    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    # now the store
    #view = LabeledCategoriesView(datadir, db, icons)
    view = CategoriesView(datadir, db, icons)
    view.connect("item-activated", category_activated, db)

    # gui
    scroll = gtk.ScrolledWindow()
    scroll.add(view)

    win = gtk.Window()
    win.add(scroll)
    view.grab_focus()
    win.set_size_request(500,200)
    win.show_all()

    gtk.main()
