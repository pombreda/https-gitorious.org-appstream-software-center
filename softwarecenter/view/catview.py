import gtk
import atk
import gobject
import cairo
import pango
import pangocairo

import gettext
import glib
import glob
import locale
import logging
import os
import xapian

from widgets import pathbar_common
from appview import AppStore
from softwarecenter.db.database import Application

from ConfigParser import ConfigParser
from gettext import gettext as _
from xml.etree import ElementTree as ET

from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.utils import *
from softwarecenter.distro import get_distro


# shapes
SHAPE_RECTANGLE = 0
SHAPE_MID_RECT = 1
SHAPE_START_RECT = 2
SHAPE_END_RECT = 3

# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

STYLE_CATVIEW_BORDER_WIDTH = 3
STYLE_CATVIEW_VSPACING = 10    # vertical spacing between page elements
STYLE_CATVIEW_HEADER_VGRADIENT_COLOR = '#C5809D'   # the color of that purple-ish vertical gradient

STYLE_TITLE_FONT_SIZE = 20
STYLE_TITLE_XALIGNMENT = 0.0    # 0.0=left margin, 0.5=centered, 1.0=right margin

STYLE_FEATURED_FONT_SIZE = 10
STYLE_FEATURED_BORDER_WIDTH = 4
STYLE_FEATURED_FONT_COLOR = '#FFF'
STYLE_FEATURED_ARROW_WIDTH = 12
STYLE_FEATURED_XALIGNMENT = 0.0 # 0.0=left margin, 0.5=centered, 1.0=right margin
STYLE_FEATURED_LABEL_XALIGNMENT = 0.3   # 0.0=left margin, 0.5=centered, 1.0=right margin
STYLE_FEATURED_BASE_COLOR = '#F15D22'   # an orange color from which we shade, lighten, darken and mix

STYLE_DEPARTMENTS_TITLE_FONT_SIZE = 10

STYLE_LAYOUTVIEW_BORDER_WIDTH = 6
STYLE_LAYOUTVIEW_VSPACING = 14   # the vertical spacing between rows in Departments section
STYLE_LAYOUTVIEW_HSPACING = 8  # the horiz spacing between each department button

STYLE_FRAME_FILL_COLOR = '#FAFAFA'
STYLE_FRAME_OUTLINE_COLOR = '#BAB7B5'
STYLE_FRAME_HEADER_FILL_COLOR = '#DAD7D3'
STYLE_FRAME_CORNER_RADIUS = 4

STYLE_CAT_BUTTON_WIDTH = 108
STYLE_CAT_BUTTON_MIN_HEIGHT = 96
STYLE_CAT_BUTTON_BORDER_WIDTH = 6
STYLE_CAT_BUTTON_CORNER_RADIUS = 8
STYLE_CAT_BUTTON_VSPACING = 4   # vertical space between dept. icon and dept. label
STYLE_CAT_BUTTON_LABEL_FONT_SIZE = 9

STYLE_COMPACT_BUTTON_WIDTH = 168
STYLE_COMPACT_BUTTON_BORDER_WIDTH = 6
STYLE_COMPACT_BUTTON_CORNER_RADIUS = 3
STYLE_COMPACT_BUTTON_HSPACING = 4
STYLE_COMPACT_BUTTON_LABEL_FONT_SIZE = 9

STYLE_SHORTLIST_VSPACING = 8
STYLE_SHORTLIST_BORDER_WIDTH = 4

# markup / strings
# "%s" locations are where strings/vars get substituted in at runtime
# all markup must be compliant Pango Markup Language
MARKUP_VARIABLE_SIZE_LABEL = '<span size="%s">%s</span>'
MARKUP_VARIABLE_SIZE_COLOR_LABEL = '<span size="%s" color="%s">%s</span>'



(COL_CAT_NAME,
 COL_CAT_PIXBUF,
 COL_CAT_QUERY,
 COL_CAT_MARKUP) = range(4)


def get_category_by_name(categories, untrans_name):
    # find a specific category
    cat = filter(lambda cat: cat.untranslated_name == untrans_name,
                 categories)[0]
    return cat


class Category(object):
    """represents a menu category"""
    def __init__(self, untranslated_name, name, iconname, query,
                 only_unallocated, dont_display, subcategories):
        self.name = name
        self.untranslated_name = untranslated_name
        self.iconname = iconname
        self.query = query
        self.only_unallocated = only_unallocated
        self.subcategories = subcategories
        self.dont_display = dont_display


class CategoriesView(gtk.ScrolledWindow):

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (gobject.TYPE_PYOBJECT, ),
                              ),

        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  )
        }

    def __init__(self, datadir, desktopdir, cache, db, icons, apps_filter, apps_limit=0, root_category=None):
        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        db - a Database object
        icons - a gtk.IconTheme
        root_category - a Category class with subcategories or None
        """
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)

        self.vbox = gtk.VBox(spacing=STYLE_CATVIEW_VSPACING)
        self.vbox.set_border_width(STYLE_CATVIEW_BORDER_WIDTH)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.vbox)
        self.add(viewport)
        self.vbox.set_redraw_on_allocate(False)

        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        self.carosel = None
        self.departments = None
        self.categories = []
        self.header = ""
        self.cache = cache
        self.db = db
        self.icons = icons
        self.apps_filter = apps_filter
        self.apps_limit = apps_limit
        self._prev_width = 0

        if not root_category:
            self.header = _("Departments")
            self.categories = self.parse_applications_menu(desktopdir)
            self.in_subsection = False
            self._build_home_page_view()
        else:
            self.in_subsection = True
            self.set_subcategory(root_category)

        self.vbox.connect('expose-event', self._on_expose)
        self.connect('size-allocate', self._on_allocate)
        return

    def _build_home_page_view(self):
        # these methods add sections to the page
        # changing order of methods changes order they appear in the page
        self._append_featured()
        self._append_departments()
        return

    def _build_subcat_view(self):
        # these methods add sections to the page
        # changing order of methods changes order they appear in the page
        self._append_subcat_departments()
        return

    def _append_title(self):
        self.title = gtk.Label()

        # define the font size (font_size in pixels * pango.SCALE)
        size = STYLE_TITLE_FONT_SIZE*pango.SCALE
        # define the markup for the title

        self.title.set_markup(MARKUP_VARIABLE_SIZE_LABEL % (size, _('Ubuntu Software Center')))

        # align the markup to the left margin
        align = gtk.Alignment(STYLE_TITLE_XALIGNMENT, 0.5)
        align.add(self.title)

        # append the title to the page
        self.vbox.pack_start(align, False)
        return

    def _append_featured(self):
        featured_cat = get_category_by_name(self.categories,
                                            'Featured Applications')
        query = self.db.get_query_list_from_search_entry('', featured_cat.query)

        featured_apps = AppStore(self.cache,
                                 self.db,
                                 self.icons,
                                 query,
                                 self.apps_limit,
                                 True,
                                 self.apps_filter)

        carosel = FeaturedView(featured_apps)
        carosel.more_btn.connect('clicked', self._on_category_clicked, featured_cat)

        self.carosel = carosel
        self.vbox.pack_start(carosel, False)
        return


    def _append_departments(self):
        # create departments widget
        self.departments = LayoutView()

        # define the size of the departments section label
        size = STYLE_DEPARTMENTS_TITLE_FONT_SIZE*pango.SCALE
        # set the departments section to use the label markup we have just defined
        self.departments.set_label_markup(MARKUP_VARIABLE_SIZE_LABEL % (size, self.header))

#        enquirer = xapian.Enquire(self.db.xapiandb)

        # for each department append it to the department widget
        size = STYLE_CAT_BUTTON_LABEL_FONT_SIZE*pango.SCALE
        for cat in self.categories[:-1]:
            # make sure the string is parsable by pango, i.e. no funny characters
            name = gobject.markup_escape_text(cat.name.strip())
            markup = MARKUP_VARIABLE_SIZE_LABEL % (size, name)
            # define the icon of the department
            ico = gtk.image_new_from_icon_name(cat.iconname, gtk.ICON_SIZE_DIALOG)
            # finally, create the department with label markup and icon

            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

 #           markup += '<span size="%s" fgcolor="#7F7F7F">\n(%s)</span>' % (size, estimate)

            cat_btn = CategoryButton(markup, image=ico)
            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # append the departments section to the page
        self.vbox.pack_start(self.departments, False)
        return

    def _append_subcat_departments(self):
        # create departments widget
        if not self.departments:
            self.departments = LayoutView()
            # append the departments section to the page
            self.vbox.pack_start(self.departments, False)
            self.departments.show_all()
        else:
            self.departments.clear_all()

        # define the size of the departments section label
        size = STYLE_DEPARTMENTS_TITLE_FONT_SIZE*pango.SCALE
        # set the departments section to use the label markup we have just defined
        header = gobject.markup_escape_text(self.header.strip())
        self.departments.set_label_markup(MARKUP_VARIABLE_SIZE_LABEL % (size, header))

        size = STYLE_CAT_BUTTON_LABEL_FONT_SIZE*pango.SCALE
        for cat in self.categories:
            # make sure the string is parsable by pango, i.e. no funny characters
            name = gobject.markup_escape_text(cat.name.strip())
            markup = MARKUP_VARIABLE_SIZE_LABEL % (size, name)
            # define the icon of the department
            ico = gtk.image_new_from_icon_name(cat.iconname, gtk.ICON_SIZE_DIALOG)

            # finally, create the department with label markup and icon
            cat_btn = CategoryButton(markup, image=ico)
            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # kinda hacky ...
        best_fit = self._get_layout_best_fit_width()
        self.departments.build_view(best_fit)
        return

    def _on_app_clicked(self, btn, app):
        appname = app[AppStore.COL_APP_NAME]
        pkgname = app[AppStore.COL_PKGNAME]
        popcon = app[AppStore.COL_POPCON]
        self.emit("application-activated", Application(appname, pkgname, popcon))
        return False

    def _on_category_clicked(self, cat_btn, cat):
        """emit the category-selected signal when a category was clicked"""
        logging.debug("on_category_changed: %s" % cat.name)
        self.emit("category-selected", cat)
        return

    def _get_layout_best_fit_width(self):
        # sum of all border widths * 2
        if not self.parent: return 1
        bw = 2*(STYLE_CATVIEW_BORDER_WIDTH + STYLE_LAYOUTVIEW_BORDER_WIDTH)
        return self.parent.allocation.width - bw

    def _on_allocate(self, widget, allocation):
        if self._prev_width != widget.parent.allocation.width:
            self._prev_width = widget.parent.allocation.width
            best_fit = self._get_layout_best_fit_width()

            if self.carosel:
                #self.carosel.clear_rows()
                self.carosel.build_view(best_fit)
            if self.departments:
                self.departments.clear_rows()
                self.departments.build_view(best_fit)

        def idle_redraw():
            self.queue_draw()
            return False

        self.queue_draw()
        gobject.idle_add(idle_redraw)   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip()

        if not self.in_subsection:
            # draw featured carosel
            self.carosel.draw(cr, self.carosel.allocation, expose_area)

        # draw departments
        self.departments.draw(cr, self.departments.allocation, expose_area)

        del cr
        return

    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name)) 

    def _cat_sort_cmp(self, a, b):
        """sort helper for the categories sorting"""
        #print "cmp: ", a.name, b.name
        if a.untranslated_name == "System":
            return 1
        elif b.untranslated_name == "System":
            return -1
        elif a.untranslated_name == "Developer Tools":
            return 1
        elif b.untranslated_name == "Developer Tools":
            return -1
        return locale.strcoll(a.name, b.name)

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

    def _parse_and_or_not_tag(self, element, query, xapian_op):
        """parse a <And>, <Or>, <Not> tag """
        for and_elem in element.getchildren():
            if and_elem.tag == "Not":
                query = self._parse_and_or_not_tag(and_elem, query, xapian.Query.OP_AND_NOT)
            elif and_elem.tag == "Category":
                logging.debug("adding: %s" % and_elem.text)
                q = xapian.Query("AC"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCSection":
                logging.debug("adding section: %s" % and_elem.text)
                # we have the section once in apt-xapian-index and once
                # in our own DB this is why we need two prefixes
                # FIXME: ponder if it makes sense to simply write
                #        out XS in update-software-center instead of AE?
                q = xapian.Query(xapian.Query.OP_OR,
                                 xapian.Query("XS"+and_elem.text.lower()),
                                 xapian.Query("AE"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCType":
                logging.debug("adding type: %s" % and_elem.text)
                q = xapian.Query("AT"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCChannel":
                logging.debug("adding channel: %s" % and_elem.text)
                q = xapian.Query("AH"+and_elem.text.lower())
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgname":
                logging.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                q1 = xapian.Query("AP"+and_elem.text.lower())
                q = xapian.Query(xapian.Query.OP_OR, q1,
                                 xapian.Query("XP"+and_elem.text.lower()))
                query = xapian.Query(xapian_op, query, q)
            elif and_elem.tag == "SCPkgnameWildcard":
                logging.debug("adding tag: %s" % and_elem.text)
                # query both axi and s-c
                s = "pkg_wildcard:%s" % and_elem.text.lower()
                q = self.db.xapian_parser.parse_query(s, xapian.QueryParser.FLAG_WILDCARD)
                query = xapian.Query(xapian_op, query, q)
            else: 
                print "UNHANDLED: ", and_elem.tag, and_elem.text
        return query

    def _parse_include_tag(self, element):
        for include in element.getchildren():
            if include.tag == "Or":
                query = xapian.Query()
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_OR)
            if include.tag == "And":
                query = xapian.Query("")
                return self._parse_and_or_not_tag(include, query, xapian.Query.OP_AND)
            # without "and" tag we take the first entry
            elif include.tag == "Category":
                return xapian.Query("AC"+include.text.lower())
            else:
                logging.warn("UNHANDLED: _parse_include_tag: %s" % include.tag)
        # empty query matches all
        return xapian.Query("")

    def _parse_menu_tag(self, item):
        name = None
        untranslated_name = None
        query = None
        icon = None
        only_unallocated = False
        dont_display = False
        subcategories = []
        for element in item.getchildren():
            # ignore inline translations, we use gettext for this
            if (element.tag == "Name" and 
                '{http://www.w3.org/XML/1998/namespace}lang' in element.attrib):
                continue
            if element.tag == "Name":
                untranslated_name = element.text
                # gettext/xml writes stuff from software-center.menu
                # out into the pot as escaped xml, so we need to escape
                # the name first, get the translation and unscape it again
                escaped_name = xml_escape(untranslated_name)
                name = xml_unescape(gettext.gettext(escaped_name))
            elif element.tag == "SCIcon":
                icon = element.text
            elif element.tag == "Directory":
                (untranslated_name, name, gettext_domain, icon) = self._parse_directory_tag(element)
            elif element.tag == "Include":
                query = self._parse_include_tag(element)
            elif element.tag == "OnlyUnallocated":
                only_unallocated = True
            elif element.tag == "SCDontDisplay":
                dont_display = True
            elif element.tag == "Menu":
                subcat = self._parse_menu_tag(element)
                if subcat:
                    subcategories.append(subcat)
            else:
                print "UNHANDLED tag in _parse_menu_tag: ", element.tag
                
        if untranslated_name and query:
            return Category(untranslated_name, name, icon, query,  only_unallocated, dont_display, subcategories)
        else:
            print "UNHANDLED entry: ", name, untranslated_name, icon, query
        return None

    def _build_unallocated_queries(self, categories):
        for cat_unalloc in categories:
            if not cat_unalloc.only_unallocated:
                continue
            for cat in categories:
                if cat.name != cat_unalloc.name:
                    cat_unalloc.query = xapian.Query(xapian.Query.OP_AND_NOT, cat_unalloc.query, cat.query)
            #print cat_unalloc.name, cat_unalloc.query
        return

    def set_subcategory(self, root_category, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name
        self.categories = root_category.subcategories
        self._build_subcat_view()
        return

    def parse_applications_menu(self, datadir):
        " parse a application menu and return a list of Category objects"""
        categories = []
        # we support multiple menu files and menu drop ins
        menu_files = [datadir+"/desktop/software-center.menu"]
        menu_files += glob.glob(datadir+"/menu.d/*.menu")
        for f in menu_files:
            tree = ET.parse(f)
            root = tree.getroot()
            for child in root.getchildren():
                category = None
                if child.tag == "Menu":
                    category = self._parse_menu_tag(child)
                if category:
                    categories.append(category)
        # post processing for <OnlyUnallocated>
        # now build the unallocated queries, once for top-level,
        # and for the subcategories. this means that subcategories
        # can have a "OnlyUnallocated/" that applies only to 
        # unallocated entries in their sublevel
        for cat in categories:
            self._build_unallocated_queries(cat.subcategories)
        self._build_unallocated_queries(categories)

        # debug print
        for cat in categories:
            logging.debug("%s %s %s" % (cat.name, cat.iconname, cat.query))
        return categories


class FramedSection(gtk.VBox):

    def __init__(self, label_markup=None):
        gtk.VBox.__init__(self)

        self.set_border_width(STYLE_LAYOUTVIEW_BORDER_WIDTH)
        self.set_redraw_on_allocate(False)

        self.header = gtk.HBox()
        self.body = gtk.VBox()
        #self.footer = gtk.HBox()

        align = gtk.Alignment(0.5, 0.5)
        align.add(self.body)

        self.pack_start(self.header, False)
        self.pack_start(align)
        #self.pack_start(self.footer, False)

        self.label = gtk.Label()
        self.header.pack_start(self.label, False)
        self.has_label = False

        if label_markup:
            self.set_label_markup(label_markup)
        return

    def set_label_markup(self, markup):
        self.label.set_markup(markup)
        self.has_label = True

        # atk stuff
        acc = self.get_accessible()
        acc.set_name(self.label.get_text())
        acc.set_role(atk.ROLE_SECTION)
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return

        cr.save()
        x, y, w, h = a.x, a.y, a.width, a.height
        cr.rectangle(x-2, y-2, w+4, h+4)
        cr.clip()

        # fill frame light gray
        rounded_rectangle(cr, a.x+1, a.y+1, a.width-1, a.height-1, STYLE_FRAME_CORNER_RADIUS-1)
        cr.set_source_rgb(*floats_from_string(STYLE_FRAME_FILL_COLOR))
        cr.fill()

        # fill header bg
        if self.has_label:
            total_spacing = self.header.allocation.y - a.y
            h = self.header.allocation.height + 2*total_spacing

            r, g, b = floats_from_string(STYLE_FRAME_HEADER_FILL_COLOR)
            lin = cairo.LinearGradient(0, a.y, 0, a.y+h)
            lin.add_color_stop_rgba(0.0, r, g, b, 1.0)
            lin.add_color_stop_rgba(1.0, r, g, b, 0.6)

            rounded_rectangle_irregular(cr,
                                        a.x, a.y,
                                        a.width, h,
                                        (STYLE_FRAME_CORNER_RADIUS, STYLE_FRAME_CORNER_RADIUS, 0, 0))

            cr.set_source(lin)
            cr.fill()

        # highlight
        rounded_rectangle(cr, a.x+1, a.y+1, a.width-2, a.height-2, STYLE_FRAME_CORNER_RADIUS-1)
        cr.set_source_rgba(1,1,1,0.45)
        cr.stroke()

        # stroke frame outline and shadow
        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)

        # set darker gray
        r, g, b = floats_from_string(STYLE_FRAME_OUTLINE_COLOR)

        cr.set_source_rgb(r,g,b)
        rounded_rectangle(cr, a.x, a.y, a.width-1, a.height-1, STYLE_FRAME_CORNER_RADIUS)
        cr.stroke()

        #cr.set_source_rgba(r,g,b, 0.4)
        #rounded_rectangle(cr, a.x-1, a.y-1, a.width+1, a.height+1, STYLE_FRAME_CORNER_RADIUS+1)
        #cr.stroke()

        #cr.set_source_rgba(r,g,b, 0.1)
        #rounded_rectangle(cr, a.x-2, a.y-2, a.width+3, a.height+3, STYLE_FRAME_CORNER_RADIUS+2)
        #cr.stroke()

        if self.has_label:
            cr.set_source_rgba(r, g, b, 0.6)
            cr.move_to(a.x, a.y + h + 1)
            cr.rel_line_to(a.width-1, 0)
            cr.stroke()

        cr.restore()
        return


class LayoutView(FramedSection):

    def __init__(self, vspacing=STYLE_LAYOUTVIEW_VSPACING, \
                    hspacing=STYLE_LAYOUTVIEW_HSPACING):

        FramedSection.__init__(self)
        self.set_spacing(vspacing)
        self.body.set_spacing(2)
        self.hspacing = hspacing

        self.set_border_width(STYLE_LAYOUTVIEW_BORDER_WIDTH)
        self.set_redraw_on_allocate(False)
        self.widget_list = []

        self.theme = CategoryViewStyle(self)
        self._prev_width = 0
        return

    def _on_allocate(self, widget, allocation):
        if self._prev_width == allocation.width: return
        self._prev_width = allocation.width
        self._clear_rows()
        self.build_view()
        return

    def append(self, widget):
        self.widget_list.append(widget)
        return

    def build_view(self, max_width):
        row = LayoutRow(self.hspacing)
        self.body.pack_start(row, False)

        spacing = self.hspacing
        max_width -= 2*STYLE_LAYOUTVIEW_BORDER_WIDTH
        w = 0

        for cat in self.widget_list:
            cw = cat.calc_width(self)

            if w + cw + spacing < max_width:
                row.pack_start(cat, False)
                w += cw + spacing
            else:
                row = LayoutRow(self.hspacing)
                self.body.pack_start(row, False)
                row.pack_start(cat, False)
                w = cw + spacing

        self.show_all()
        return

    def clear_all(self):
        self.widget_list = []
        for row in self.body.get_children():
            for child in row.get_children():
                child.destroy()
            row.destroy()
        return

    def clear_rows(self):
        for row in self.body.get_children():
            for cat in row.hbox.get_children():
                row.hbox.remove(cat)
            row.destroy()
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return

        cr.save()
        FramedSection.draw(self, cr, a, expose_area)

        for cat in self.widget_list:
            a = cat.allocation
            if a.width == 1 or a.height == 1: break
            cat.draw(cr, a, expose_area, self.theme)

        cr.restore()
        return


class LayoutRow(gtk.Alignment):

    def __init__(self, hspacing):
        gtk.Alignment.__init__(self, 0.5, 0.5)
        self.hbox = gtk.HBox(spacing=hspacing)
        self.set_redraw_on_allocate(False)
        self.hbox.set_redraw_on_allocate(False)
        self.add(self.hbox)
        return

    def __getitem__(self, index):
        return self.hbox.get_children()[index]

    def pack_start(self, cat, *args, **kwargs):
        self.hbox.pack_start(cat, *args, **kwargs)
        return

    def pack_end(self, cat, *args, **kwargs):
        self.hbox.pack_end(cat, *args, **kwargs)
        return


class FeaturedView(FramedSection):

    def __init__(self, featured_apps, vspacing=STYLE_LAYOUTVIEW_VSPACING, \
                    hspacing=STYLE_LAYOUTVIEW_HSPACING):

        FramedSection.__init__(self)
        self.set_spacing(vspacing)
        self.body.set_spacing(6)
        self.hbox = gtk.HBox(spacing=hspacing)
        self.body.pack_start(self.hbox)
        self.hbox.set_homogeneous(True)

        self.posters = (FeaturedPoster(32),
                        FeaturedPoster(32),
                        FeaturedPoster(32))

        for poster in self.posters:
            self.hbox.pack_start(poster)

        self.set_border_width(STYLE_LAYOUTVIEW_BORDER_WIDTH)
        self.set_redraw_on_allocate(False)

        name = 'Showcase'
        size = STYLE_DEPARTMENTS_TITLE_FONT_SIZE*pango.SCALE
        self.set_label_markup(MARKUP_VARIABLE_SIZE_LABEL % (size, name))

        self.featured_apps = featured_apps

        self.more_btn = MoreButton('<span color="#FFF"><big><i>Want to see more?</i> Browse all featured applications...</big></span>')
        align = gtk.Alignment(1.0, 0.5)
        align.add(self.more_btn)
        self.body.pack_end(align, False)

        self._icon_size = self.featured_apps.icon_size
        self._offset = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None

        self.show_all()
        gobject.timeout_add(15000, self.transition)
        return

    def _fade_in(self):
        self._alpha += 0.1
        if self._alpha >= 1.0:
            self._alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _fade_out(self):
        self._alpha -= 0.1
        if self._alpha <= 0.0:
            self._alpha = 0.0
            self.queue_draw()
            self._set_next()
            return False
        self.queue_draw()
        return True

    def _set_next(self):
        n_posters = len(self.posters)
        if self._offset < len(self.featured_apps)-n_posters:
            self._offset += n_posters
        else:
            self._offset = 0

        for poster in self.posters:
            poster.clear_asset_cache()

        self._fader = gobject.timeout_add(50, self._fade_in)
        return

    def transition(self, loop=True):
        self._fader = gobject.timeout_add(50, self._fade_out)
        return loop

    def build_view(self, max_width):
        max_width -=  3*STYLE_LAYOUTVIEW_BORDER_WIDTH
        self.body.set_size_request(max_width, -1)
        self.more_btn.set_size_request(max_width, -1)
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return

        cr.save()
        FramedSection.draw(self, cr, a, expose_area)
        self.more_btn.draw(cr, self.more_btn.allocation, expose_area)

        if not self._layout:
            # cache a layout
            pc = self.get_pango_context()
            self._layout = pango.Layout(pc)
            self._layout.set_wrap(pango.WRAP_WORD_CHAR)

        alpha = self._alpha
        layout = self._layout

        w = self.posters[0].allocation.width
        layout.set_width((w-self._icon_size-20)*pango.SCALE)

        for i, poster in enumerate(self.posters):
            index = i+self._offset
            if index == len(self.featured_apps):
                break

            app = self.featured_apps[index]
            poster.draw(cr, poster.allocation, expose_area, app, layout, alpha)

        cr.restore()
        return


class FeaturedPoster(gtk.EventBox):

    def __init__(self, icon_size):
        gtk.EventBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_visible_window(False)
        self.set_size_request(-1, 75)

        self._icon_size = icon_size
        self._icon_pb = None
        self._icon_offset = None
        self._text = None
        self._text_extents = None

        self.set_events(gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        #self.connect("button-press-event", self._on_button_press)
        #self.connect("button-release-event", self._on_button_release)
        self.show_all()
        return

    def _on_enter(self, poster, event):
        self.set_state(gtk.STATE_PRELIGHT)
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        return

    def _on_leave(self, poster, event):
        self.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)
        return

    def clear_asset_cache(self):
        self._icon_pb = None
        self._icon_offset = None
        self._text = None
        self._text_extents = None
        return

    def draw(self, cr, a, expose_area, app, layout, alpha):
        cr.save()
        cr.rectangle(a)
        cr.clip()
        cr.translate(a.x, a.y)

        if self.state == gtk.STATE_PRELIGHT and self._text_extents:
            #h = max(38, self._text_extents[3] + 6)
            rounded_rectangle(cr, 0,0,a.width, a.height, 2)
            cr.set_source_rgba(*floats_from_string_with_alpha('#F15D22', alpha))
            cr.fill()

        if not self._icon_pb:
            self._icon_pb = app[AppStore.COL_ICON]

        if not self._icon_offset:
            pb = self._icon_pb
            pw = pb.get_width()
            ph = pb.get_height()
            px = 0
            py = 3

            # center pixbuf
            ico = self._icon_size
            if pw != ico or ph != ico:
                px = (ico-pw)/2
                py += (ico-ph)/2
            self._icon_offset = px, py

        if not self._text:
            text = app[AppStore.COL_TEXT]
            name, summary = text.splitlines()
            self._text = '<b>%s</b>\n<small>%s</small>' \
                          % (name, summary)
            layout.set_markup(self._text)
            self._text_extents = layout.get_pixel_extents()[1]

        cr.set_source_pixbuf(self._icon_pb, *self._icon_offset)
        cr.paint_with_alpha(alpha)

        if self.state == gtk.STATE_NORMAL:
            color = '#3C3B37'
        else:
            color = '#FFF'
        layout.set_markup('<span color="%s">%s</span>' % (color, self._text))
        if alpha < 1.0:
            pcr = pangocairo.CairoContext(cr)
            pcr.move_to(8 + self._icon_size, 3)
            pcr.set_source_rgba(*floats_from_string_with_alpha(color, alpha))
            pcr.layout_path(layout)
            pcr.fill()
        else:
            self.style.paint_layout(self.window,
                                    self.state,
                                    False,
                                    a,          # area
                                    self,
                                    None,
                                    a.x + 8 + self._icon_size,
                                    a.y + 3,
                                    layout)

        cr.restore()
        return


class PushButton(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self, markup, image=None):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_redraw_on_allocate(False)
        self.markup = markup
        self.label = gtk.Label()
        self.label.set_markup(markup)
        self.image = image
        self.shape = pathbar_common.SHAPE_RECTANGLE
        self.theme = pathbar_common.PathBarStyle(self)

        # atk stuff
        atk_obj = self.get_accessible()
        atk_obj.set_name(self.label.get_text())
        atk_obj.set_role(atk.ROLE_PUSH_BUTTON)

        self._children_block_draw = False
        self._layout = None
        self._button_press_origin = None    # broken
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        self.connect('focus-in-event', self._on_focus_in)
        self.connect('focus-out-event', self._on_focus_out)
        self.connect('expose-event', lambda w, e: self._children_block_draw)
        return

    def _on_enter(self, cat, event):
        if cat == self._button_press_origin:
            cat.set_state(gtk.STATE_ACTIVE)
        else:
            cat.set_state(gtk.STATE_PRELIGHT)
        self.window.set_cursor(self._cursor)
        return

    def _on_leave(self, cat, event):
        cat.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)
        return

    def _on_button_press(self, cat, event):
        if event.button != 1: return
        self._button_press_origin = cat
        cat.set_state(gtk.STATE_ACTIVE)
        return

    def _on_button_release(self, cat, event):
        if event.button != 1: return

        cat_region = gtk.gdk.region_rectangle(cat.allocation)
        if not cat_region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            return
        if cat != self._button_press_origin: return
        cat.set_state(gtk.STATE_PRELIGHT)
        self._button_press_origin = None
        self.emit('clicked')
        return

    def _on_key_press(self, cat, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            cat.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, cat, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (32, 65293, 65421):
            cat.set_state(gtk.STATE_NORMAL)
            self.emit('clicked')
        return

    def _on_focus_in(self, cat, event):
        self.queue_draw()
        return

    def _on_focus_out(self, cat, event):
        self.queue_draw()
        return

    def draw(self, cr, a, expose_area, alpha=1.0):
        if draw_skip(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        self.theme.paint_bg(cr, self, a.x, a.y, a.width-1, a.height, alpha=alpha)
        if self.has_focus() and alpha == 1.0:
            a = self.label.allocation
            x, y, w, h = a.x, a.y, a.width, a.height
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x-2, y-1, w+4, h+2),
                                   self,
                                   'button',
                                   x-2, y-1, w+4, h+2)

        if alpha != 1.0:
            self._children_block_draw = True
            # draw label with cairo
            if not self._layout:
                pc = self.get_pango_context()
                self._layout = pango.Layout(pc)

            la = self.label.allocation
            self._layout.set_markup(self.label.get_label())
            pcr = pangocairo.CairoContext(cr)
            pcr.move_to(la.x + self.get_border_width(), la.y)
            pcr.set_source_rgba(0,0,0, alpha)
            pcr.layout_path(self._layout)
        else:
            self._children_block_draw = False

        cr.restore()
        return


class CategoryButton(PushButton):

    def __init__(self, markup, image=None):
        PushButton.__init__(self, markup, image)
        self.set_border_width(STYLE_CAT_BUTTON_BORDER_WIDTH)
        self.label.set_line_wrap(gtk.WRAP_WORD)
        self.label.set_justify(gtk.JUSTIFY_CENTER)

        # determine size_request width for label
        layout = self.label.get_layout()
        layout.set_width(STYLE_CAT_BUTTON_WIDTH*pango.SCALE)
        lw, lh = layout.get_pixel_extents()[1][2:]   # ink extents width, height
        self.label.set_size_request(lw, -1)

        self.vbox = gtk.VBox(spacing=STYLE_CAT_BUTTON_VSPACING)
        h = lh + STYLE_CAT_BUTTON_VSPACING +2*STYLE_CAT_BUTTON_BORDER_WIDTH + 48 # 32 = icon size
        self.vbox.set_size_request(STYLE_CAT_BUTTON_WIDTH, max(h, STYLE_CAT_BUTTON_MIN_HEIGHT))

        self.add(self.vbox)
        if self.image:
            self.vbox.pack_start(self.image, False)

        self.vbox.pack_start(self.label)
        self.show_all()
        return

    def calc_width(self, realized_widget):
        return STYLE_CAT_BUTTON_WIDTH + 2*self.get_border_width()

    def draw(self, cr, a, expose_area, theme):
        if draw_skip(a, expose_area): return

        x, y, w, h = a.x, a.y, a.width, a.height
        r = STYLE_CAT_BUTTON_CORNER_RADIUS
        if self.state == gtk.STATE_NORMAL:
            pass
        elif self.state != gtk.STATE_ACTIVE:
            theme.paint_bg(cr, self, x, y, w, h, r)
        else:
            theme.paint_bg_active_deep(cr, self, x, y, w, h, r)

        if self.has_focus():
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x+4, y+4, w-8, h-8),
                                   self,
                                   'button',
                                   x+4, y+4, w-8, h-8)
        return


class MoreButton(PushButton):

    def __init__(self, markup):
        PushButton.__init__(self, markup, image=None)
        self.set_border_width(STYLE_FEATURED_BORDER_WIDTH)

        # override arrow width and colour palatte
        self.theme.properties['arrow_width'] = STYLE_FEATURED_ARROW_WIDTH
        self._define_custom_palatte()
        # override shape
        #self.shape = pathbar_common.SHAPE_START_ARROW

        # determine layout width
        layout = self.label.get_layout()
        lw = layout.get_pixel_extents()[1][2]   # ink extents width

        # width request
        w = lw + 8*self.get_border_width() + STYLE_FEATURED_ARROW_WIDTH
        self.set_size_request(w, -1)

        align = gtk.Alignment(0.5, 0.5)
        align.add(self.label)

        self.add(align)
        self.show_all()
        return

    def _define_custom_palatte(self):
        orange = pathbar_common.color_from_string(STYLE_FEATURED_BASE_COLOR)

        self.theme.gradients = {
            gtk.STATE_NORMAL:      (orange.shade(1.125), orange.shade(0.99)),
            gtk.STATE_ACTIVE:      (orange.shade(0.97), orange.shade(0.85)),
            gtk.STATE_SELECTED:    (orange, orange),
            gtk.STATE_PRELIGHT:    (orange.shade(1.2), orange.shade(1.1)),
            gtk.STATE_INSENSITIVE: (self.theme.theme.mid, self.theme.theme.mid)}

        self.theme.dark_line = {
            gtk.STATE_NORMAL:       orange.shade(0.65),
            gtk.STATE_ACTIVE:       orange.shade(0.65),
            gtk.STATE_PRELIGHT:     orange.darken(),
            gtk.STATE_SELECTED:     orange.shade(0.65),
            gtk.STATE_INSENSITIVE:  orange.shade(0.65)}

        self.theme.light_line = {
            gtk.STATE_NORMAL:       orange.shade(0.915),
            gtk.STATE_ACTIVE:       orange.shade(0.825),
            gtk.STATE_PRELIGHT:     orange,
            gtk.STATE_SELECTED:     orange,
            gtk.STATE_INSENSITIVE:  self.theme.theme.mid}
        return


class CategoryViewStyle:

    def __init__(self, pathbar):
        self._load_shape_map(pathbar.get_direction())
        gtk_settings = gtk.settings_get_default()
        self.theme = self._load_theme(gtk_settings)
        self.theme.build_palette(gtk_settings)
        self.properties = self.theme.get_properties(gtk_settings)
        self.gradients = self.theme.get_grad_palette()
        self.dark_line = self.theme.get_dark_line_palette()
        self.light_line = self.theme.get_light_line_palette()
        self.text = self.theme.get_text_palette()
        self.text_states = self.theme.get_text_states()
        self.base_color = None
        return

    def __getitem__(self, item):
        if self.properties.has_key(item):
            return self.properties[item]
        logging.warn('Key does not exist in the style profile: %s' % item)
        return None

    def _load_shape_map(self, direction):
        if direction != gtk.TEXT_DIR_RTL:
            self.shape_map = {SHAPE_RECTANGLE:   self._shape_rectangle,
                              SHAPE_START_RECT: self._shape_start_rect_ltr,
                              SHAPE_MID_RECT:   self._shape_mid_rect_ltr,
                              SHAPE_END_RECT:     self._shape_end_rect_ltr}
#        else:
#            self.shape_map = {SHAPE_RECTANGLE:   self._shape_rectangle,
#                              SHAPE_START_ARROW: self._shape_start_arrow_rtl,
#                              SHAPE_MID_ARROW:   self._shape_mid_arrow_rtl,
#                              SHAPE_END_CAP:     self._shape_end_cap_rtl}
        return

    def _load_theme(self, gtksettings):
        name = gtksettings.get_property("gtk-theme-name")
        r = pathbar_common.ThemeRegistry()
        return r.retrieve(name)

    def _shape_rectangle(self, cr, x, y, w, h, r, hint=None):
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_start_rect_ltr(self, cr, x, y, w, h, r, hint=None):
        cr.new_sub_path()
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def _shape_mid_rect_ltr(self, cr, x, y, w, h, r, hint=None):
        cr.rectangle(x-1, y, w-x+1, h-y)
        return

    def _shape_end_rect_ltr(self, cr, x, y, w, h, r, hint=None):
        cr.move_to(x-1, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(x-1, h)
        cr.close_path()
        return

    def _shape_start_rect_rtl(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.arc(w-r, r+y, r, 270*PI_OVER_180, 0)
        cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_mid_rect_rtl(self, cr, x, y, w, h, r):
        cr.move_to(x, (h+y)/2)
        cr.line_to(aw, y)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.line_to(aw, h)
        cr.close_path()
        return

    def _shape_end_rect_rtl(self, cr, x, y, w, h, r):
        cr.arc(r+x, r+y, r, M_PI, 270*PI_OVER_180)
        cr.line_to(w, y)
        cr.line_to(w, h)
        cr.arc(r+x, h-r, r, 90*PI_OVER_180, M_PI)
        cr.close_path()
        return

    def set_direction(self, direction):
        self._load_shape_map(direction)
        return

    def paint_bg(self, cr, cat, x, y, w, h, r):
        shape = self.shape_map[cat.shape]
        state = cat.state

        cr.save()
        cr.translate(x+0.5, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape(cr, 0, 0, w, h, r)
        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(0.0, *color1.tofloats())
        lin.add_color_stop_rgb(1.0, *color2.tofloats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner bevel/highlight
        if r == 0: w += 1
        shape(cr, 1, 1, w-1, h-1, r-1)
        cr.set_source_rgb(*self.light_line[state].tofloats())
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r)
        cr.set_source_rgb(*self.dark_line[state].tofloats())
        cr.stroke()
        cr.restore()
        return

    def paint_bg_active_shallow(self, cr, cat, x, y, w, h, r):
        shape = self.shape_map[cat.shape]
        state = cat.state

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape(cr, 0, 0, w, h, r)

        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(2.0, *color1.tofloats())
        lin.add_color_stop_rgb(0.0, *color2.tofloats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow
        if r == 0: w += 1
        red, g, b = self.dark_line[state].tofloats()
        shape(cr, 1, 1, w-1, h-1, r-1)
        cr.set_source_rgba(red, g, b, 0.4)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r)
        cr.set_source_rgb(*self.dark_line[state].tofloats())
        cr.stroke()
        cr.restore()
        return

    def paint_bg_active_deep(self, cr, cat, x, y, w, h, r):
        shape = self.shape_map[cat.shape]
        state = cat.state

        cr.save()
        cr.rectangle(x, y, w+1, h)
        cr.clip()
        cr.translate(x+0.5, y+0.5)

        w -= 1
        h -= 1

        # bg linear vertical gradient
        color1, color2 = self.gradients[state]

        shape(cr, 0, 0, w, h, r)

        lin = cairo.LinearGradient(0, 0, 0, h)
        lin.add_color_stop_rgb(2.0, *color1.tofloats())
        lin.add_color_stop_rgb(0.0, *color2.tofloats())
        cr.set_source(lin)
        cr.fill()

        cr.set_line_width(1.0)
        # inner shadow 1
        if r == 0: w += 1
        shape(cr, 2, 2, w-2, h-2, r-2)
        red, g, b = self.dark_line[state].tofloats()
        cr.set_source_rgba(red, g, b, 0.2)
        cr.stroke()

        shape(cr, 1, 1, w-1, h-1, r-1)
        cr.set_source_rgba(red, g, b, 0.4)
        cr.stroke()

        # strong outline
        shape(cr, 0, 0, w, h, r)
        cr.set_source_rgb(*self.dark_line[state].tofloats())
        cr.stroke()
        cr.restore()
        return

class Test:

    def __init__(self):
        w = gtk.Window()
        w.set_size_request(500, 400)
        w.connect('destroy', gtk.main_quit)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        w.add(scrolled)

        view = CatViewBody()
        scrolled.add_with_viewport(view)

        w.show_all()
        return

def draw_skip(widget_area, expose_area):
    return gtk.gdk.region_rectangle(expose_area).rect_in(widget_area) == gtk.gdk.OVERLAP_RECTANGLE_OUT

def floats_from_string(spec):
    color = gtk.gdk.color_parse(spec)
    return color.red_float, color.green_float, color.blue_float

def floats_from_string_with_alpha(spec, a):
    r, g, b = floats_from_string(spec)
    return r, g, b, a

def rounded_rectangle(cr, x, y, w, h, r):
    cr.save()
    cr.translate(x, y)
    cr.new_sub_path()
    cr.arc(r, r, r, M_PI, 270*PI_OVER_180)
    cr.arc(w-r, r, r, 270*PI_OVER_180, 0)
    cr.arc(w-r, h-r, r, 0, 90*PI_OVER_180)
    cr.arc(r, h-r, r, 90*PI_OVER_180, M_PI)
    cr.close_path()
    cr.restore()
    return

def rounded_rectangle_irregular(cr, x, y, w, h, corner_radii):
    nw, ne, se, sw = corner_radii
    cr.save()
    cr.translate(x, y)
    if nw:
        cr.new_sub_path()
        cr.arc(nw, nw, nw, M_PI, 270 * PI_OVER_180)
    else:
        cr.move_to(0, 0)
    if ne:
        cr.arc(w-ne, ne, ne, 270 * PI_OVER_180, 0)
    else:
        cr.rel_line_to(w-nw, 0)
    if se:
        cr.arc(w-se, h-se, se, 0, 90 * PI_OVER_180)
    else:
        cr.rel_line_to(0, h-ne)
    if sw:
        cr.arc(sw, h-sw, sw, 90 * PI_OVER_180, M_PI)
    else:
        cr.rel_line_to(-(w-se), 0)
    cr.close_path()
    cr.restore()
    return


if __name__ == '__main__':
    Test()
    gtk.main()
