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
from widgets.backforward import BackForwardButton
from appview import AppStore
from softwarecenter.db.database import Application

from ConfigParser import ConfigParser
from gettext import gettext as _
from xml.etree import ElementTree as ET

from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import unescape as xml_unescape

from softwarecenter.utils import *
from softwarecenter.distro import get_distro

from catview import *

# shapes
SHAPE_RECTANGLE = 0
SHAPE_MID_RECT = 1
SHAPE_START_RECT = 2
SHAPE_END_RECT = 3

# pi constants
M_PI = 3.1415926535897931
PI_OVER_180 = 0.017453292519943295

BORDER_WIDTH_LARGE =    6
BORDER_WIDTH_MED =    6
BORDER_WIDTH_SMALL = 3

VSPACING_XLARGE =   12
VSPACING_LARGE =    6    # vertical spacing between page elements
VSPACING_SMALL =    3

HSPACING_XLARGE =   12
HSPACING_LARGE =    6    # horizontal spacing between page elements
HSPACING_SMALL =    3

COLOR_WHITE =   '#FFF'
COLOR_BLACK =   '#3C3B37'
COLOR_ORANGE =  '#F15D22'   # hat tip OMG UBUNTU!
COLOR_PURPLE =  '#4D1F40'   # hat tip OMG UBUNTU!

COLOR_FRAME_BG_FILL =       '#FAFAFA'
COLOR_FRAME_OUTLINE =       '#BAB7B5'
COLOR_FRAME_HEADER_FILL =   '#DAD7D3'
COLOR_FRAME_LABEL =         '#707070'
FRAME_CORNER_RADIUS =       3

CAT_BUTTON_FIXED_WIDTH =    108
CAT_BUTTON_MIN_HEIGHT =     96
CAT_BUTTON_BORDER_WIDTH =   6
CAT_BUTTON_CORNER_RADIUS =  8

# MAX_POSTER_COUNT should be a number less than the number of featured apps
CAROSEL_MAX_POSTER_COUNT =      8
CAROSEL_MIN_POSTER_COUNT =      1
CAROSEL_POSTER_MIN_WIDTH =      200 # this is actually more of an approximate minima
CAROSEL_TRANSITION_TIMEOUT =    20000 # n_seconds * 1000
CAROSEL_FADE_INTERVAL =         50 # msec  
CAROSEL_FADE_STEP =             0.2 # value between 0.0 and 1.0
POSTER_CORNER_RADIUS =          3

H1 = '<big><b>%s<b></big>'
H2 = '<big>%s</big>'
H3 = '<b>%s</b>'
H4 = '%s'
H5 = '<small><b>%s</b></small>'

P =  '%s'
P_SMALL = '<small>%s</small>'


class CategoriesViewGtk(gtk.ScrolledWindow, CategoriesView):

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
        CategoriesView.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.set_shadow_type(gtk.SHADOW_NONE)

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox = gtk.VBox(spacing=VSPACING_XLARGE)
        self.vbox.set_border_width(BORDER_WIDTH_LARGE)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.vbox)
        self.add(viewport)
        self.vbox.set_redraw_on_allocate(False)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # append sections
        self.carosel = None
        self.departments = None
        self.welcome = None

        # appstore stuff
        self.categories = []
        self.cache = cache
        self.db = db
        self.icons = icons
        self.header = ''
        self.apps_filter = apps_filter
        self.apps_limit = apps_limit

        # more stuff
        self._prev_width = 0
        self._poster_sigs = []

        # FIXME: move this to shared code
        if not root_category:
            self.categories = self.parse_applications_menu(desktopdir)
            self.in_subsection = False
            self.header = _('Departments')
            self._build_homepage_view()
        else:
            self.in_subsection = True
            self.set_subcategory(root_category)

        self.vbox.connect('expose-event', self._on_expose)
        self.connect('size-allocate', self._on_allocate)

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        #self._append_welcome()
        self._append_featured()
        self._append_departments()
        return

    def _build_subcat_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments()
        return

    def _append_featured(self):
        featured_cat = get_category_by_name(self.categories,
                                            'Featured Applications')    # untranslated name
        query = self.db.get_query_list_from_search_entry('', featured_cat.query)

        featured_apps = AppStore(self.cache,
                                 self.db,
                                 self.icons,
                                 query,
                                 self.apps_limit,
                                 True,
                                 self.apps_filter)

        carosel = FeaturedView(featured_apps)
        carosel.more_btn.connect('clicked',
                                 self._on_category_clicked,
                                 featured_cat)
 
        #carosel.show_hide_btn.connect('clicked',
                                      #self._on_show_hide_carosel_clicked,
                                      #carosel)

        self.carosel = carosel
        self.vbox.pack_start(carosel, False)
        return

    def _append_welcome(self):
        self.welcome = WelcomeView()
        self.vbox.pack_start(self.welcome, False)
        return

    def _full_redraw(self):
        def _redraw():
            self.queue_draw()
            return False

        self.queue_draw()
        gobject.idle_add(_redraw)
        return

    def _append_departments(self):
        # create departments widget
        self.departments = LayoutView()

        # set the departments section to use the label markup we have just defined
        self.departments.set_label(H2 % self.header)

#        enquirer = xapian.Enquire(self.db.xapiandb)

        for cat in self.categories[:-1]:
            # make sure the string is parsable by pango, i.e. no funny characters
            name = gobject.markup_escape_text(cat.name.strip())
            # define the icon of the department
            ico = gtk.image_new_from_icon_name(cat.iconname, gtk.ICON_SIZE_DIALOG)
            # finally, create the department with label markup and icon

            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

            cat_btn = CategoryButton(name, image=ico)
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

        # set the departments section to use the label markup we have just defined
        header = gobject.markup_escape_text(self.header)
        self.departments.set_label(H2 % header)

        for cat in self.categories:
            # make sure the string is parsable by pango, i.e. no funny characters
            name = gobject.markup_escape_text(cat.name)
            # define the icon of the department
            ico = gtk.image_new_from_icon_name(cat.iconname, gtk.ICON_SIZE_DIALOG)

            # finally, create the department with label markup and icon
            cat_btn = CategoryButton(name, image=ico)
            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # kinda hacky doing this here...
        best_fit = self._get_layout_best_fit_width()
        self.departments.set_width(best_fit)
        return

    def _on_app_clicked(self, btn):
        app = btn.app
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

    def _on_show_hide_carosel_clicked(self, btn, carosel):
        carosel_visible = self.carosel.get_carosel_visible()
        if carosel_visible:
            carosel.show_carosel(False)
        else:
            carosel.show_carosel(True)
            self._cleanup_poster_sigs()

        self._full_redraw()
        return

    def _get_layout_best_fit_width(self):
        if not self.parent: return 1
        # parent alllocation less the sum of all border widths
        return self.parent.allocation.width - 2*BORDER_WIDTH_LARGE - 2*BORDER_WIDTH_MED

    def _on_allocate(self, widget, allocation):
        if self._prev_width != widget.parent.allocation.width:
            self._prev_width = widget.parent.allocation.width
            best_fit = self._get_layout_best_fit_width()

            if self.carosel:
                self.carosel.set_width(best_fit)
                self._cleanup_poster_sigs()
            if self.departments:
                self.departments.clear_rows()
                self.departments.set_width(best_fit)

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        #cr.clip()
        cr.clip_preserve()

        cr.set_source_rgb(*floats_from_string(COLOR_FRAME_BG_FILL))
        cr.fill()

        # draw departments
        self.departments.draw(cr, self.departments.allocation, expose_area)

        if not self.in_subsection:
            # draw featured carosel
            self.carosel.draw(cr, self.carosel.allocation, expose_area)
            # draw welcome and ubuntu software-center branding etc
            #self.welcome.draw(cr, self.welcome.allocation, expose_area)

        del cr
        return

    def _cleanup_poster_sigs(self):
        # clean-up and connect signal handlers
        for sig_id in self._poster_sigs:
            gobject.source_remove(sig_id)
        self._poster_sigs = []
        for poster in self.carosel.posters:
            self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))
        return

    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name)) 

    def set_subcategory(self, root_category, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name
        self.categories = root_category.subcategories
        self._build_subcat_view()
        return


class FramedSection(gtk.VBox):

    def __init__(self, label_markup=None):
        gtk.VBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_spacing(VSPACING_LARGE)

        self.header = gtk.HBox()
        self.body = gtk.VBox()

        self.header.set_border_width(BORDER_WIDTH_MED)
        self.body.set_border_width(BORDER_WIDTH_MED)
        self.body.set_spacing(VSPACING_SMALL)

        align = gtk.Alignment(0.5, 0.5)
        align.add(self.body)

        self.pack_start(self.header, False)
        self.pack_start(align)
        #self.pack_start(self.footer, False)

        self.label = EngravedLabel()
        self.header.pack_start(self.label, False)
        self.has_label = False

        if label_markup:
            self.set_label(label_markup)
        return

    def set_label(self, label):
        self.label.set_text(label)
        self.has_label = True

        # atk stuff
        acc = self.get_accessible()
        acc.set_name(self.label.get_text())
        acc.set_role(atk.ROLE_SECTION)
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        # fill section white
        cr.rectangle(a)
        cr.set_source_rgb(1, 1, 1)
        cr.fill_preserve()

        cr.save()
        cr.set_line_width(1)
        cr.translate(0.5, 0.5)
        cr.set_source_rgb(*floats_from_string(COLOR_PURPLE))
        cr.stroke()
        cr.restore()

        # header gradient - suppose to be ubuntu wallpaper-esque
        pink = '#FCE3DD'
        h = 48
        r, g, b = floats_from_string(pink)
        lin = cairo.LinearGradient(0, a.y+1, 0, a.y+h)
        lin = cairo.LinearGradient(0, a.y+1, 0, a.y+h)
        lin.add_color_stop_rgba(0.0, r, g, b, 0.85)
        lin.add_color_stop_rgba(1.0, r, g, b, 0)
        cr.rectangle(a.x+1, a.y+1, a.width-2, h)
        cr.set_source(lin)
        cr.fill()

        self.label.draw(cr, self.label.allocation, expose_area)

        cr.restore()
        return


class LayoutView(FramedSection):

    def __init__(self):

        FramedSection.__init__(self)
        self.hspacing = HSPACING_SMALL

        self.set_redraw_on_allocate(False)
        self.widget_list = []

        self.theme = pathbar_common.PathBarStyle(self)
        self._prev_width = 0
        return

    def _on_allocate(self, widget, allocation):
        if self._prev_width == allocation.width: return
        self._prev_width = allocation.width
        self._clear_rows()
        self.set_width()
        return

    def append(self, widget):
        self.widget_list.append(widget)
        return

    def set_width(self, width):
        row = LayoutRow(self.hspacing)
        self.body.pack_start(row, False)

        spacing = self.hspacing
        width -= 3*BORDER_WIDTH_MED
        w = 0

        for cat in self.widget_list:
            cw = cat.calc_width(self)

            if w + cw + spacing <= width:
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

    def __init__(self, featured_apps):
        FramedSection.__init__(self)
        self.hbox = gtk.HBox(spacing=HSPACING_SMALL)
        self.body.pack_start(self.hbox)
        self.hbox.set_homogeneous(True)
        self.header.set_spacing(HSPACING_SMALL)

        self.footer = gtk.HBox()
        self.footer.set_border_width(BORDER_WIDTH_MED)
        self.pack_end(self.footer)

        self.posters = []
        self.n_posters = 0
        self._show_carosel = True

        self.set_redraw_on_allocate(False)
        self.featured_apps = featured_apps

        self.set_label(H2 % _('Featured Applications'))

        # show all featured apps orange button

        # \xbb == U+00BB == RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK == guillemotright
        label = u'View all Featured Applications \xbb'
        self.more_btn = BasicButton('<span color="%s"><small>%s</small></span>' % (COLOR_WHITE, label))
        #self.more_btn.set_shape(pathbar_common.SHAPE_START_ARROW)
        # override theme palatte with orange palatte
        self.more_btn.use_flat_palatte()
        self.header.pack_end(self.more_btn, False)

        ## show / hide header button
        #self._hide_label = '<small>%s</small>' % _('Hide')
        #self._show_label = '<small>%s</small>' % _('Show')
        #self.show_hide_btn = BasicButton(self._hide_label)
        #self.header.pack_end(self.show_hide_btn, False)

        # back forward button to allow user control of carosel
        self.back_forward_btn = BackForwardButton(part_size=(24,19),
                                                  native_draw=False)

        self.back_forward_btn.set_use_hand_cursor(True)
        self.back_forward_btn.connect('left-clicked', self._on_left_clicked)
        self.back_forward_btn.connect('right-clicked', self._on_right_clicked)
        self.footer.pack_end(self.back_forward_btn, False)

        self._width = 0
        self._icon_size = self.featured_apps.icon_size
        self._offset = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None

        self.show_all()

        # cache a pango layout for text ops and overlay image for installed apps
        self._cache_layout()
        self._cache_overlay_image("software-center-installed")

        # init asset cache for each poster
        self._set_next()

        # start the carosel
        self.start()
        return

    def _cache_overlay_image(self, overlay_icon_name, overlay_size=16):
        icons = gtk.icon_theme_get_default()
        try:
            self._overlay = icons.load_icon(overlay_icon_name,
                                            overlay_size, 0)
        except glib.GError:
            # icon not present in theme, probably because running uninstalled
            self._overlay = icons.load_icon('emblem-system',
                                            overlay_size, 0)
        return

    def _cache_layout(self):
        # cache a layout
        pc = self.get_pango_context()
        self._layout = pango.Layout(pc)
        self._layout.set_wrap(pango.WRAP_WORD_CHAR)
        return

    def _remove_all_posters(self):
        # clear posters
        for poster in self.posters:
            self.hbox.remove(poster)
            poster.destroy()
        self.posters = []
        return

    def _build_view(self, width):
        # push the offset back, so when we recache assets do so from the
        # starting point we were at in the previous incarnation
        self._offset -= self.n_posters

        # number of posters we should have given available space
        n = width / CAROSEL_POSTER_MIN_WIDTH
        n = max(CAROSEL_MIN_POSTER_COUNT, n)
        n = min(CAROSEL_MAX_POSTER_COUNT, n)
        self.n_posters = n    

        # repack appropriate number of new posters
        for i in range(n):
            poster = FeaturedPoster(32)
            self.posters.append(poster)
            self.hbox.pack_start(poster)

            if self._offset == len(self.featured_apps):
                    self._offset = 0
            poster.cache_assets(self.featured_apps[self._offset], self._layout)
            self._offset += 1

        self.hbox.show_all()
        return

    def _fade_in(self):
        self._alpha += CAROSEL_FADE_STEP
        if self._alpha >= 1.0:
            self._alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _fade_out(self):
        self._alpha -= CAROSEL_FADE_STEP
        if self._alpha <= 0.0:
            self._alpha = 0.0
            self.queue_draw()
            self._set_next()
            return False
        self.queue_draw()
        return True

    def _set_next(self, fade_in=True):
        # increment view and update asset cache for each poster
        for poster in self.posters:
            if self._offset == len(self.featured_apps):
                    self._offset = 0
            poster.cache_assets(self.featured_apps[self._offset], self._layout)
            self._offset += 1
        if fade_in:
            self._fader = gobject.timeout_add(CAROSEL_FADE_INTERVAL,
                                              self._fade_in)
        else:
            self._alpha = 1.0
            self.queue_draw()
        return

    def _on_left_clicked(self, btn, event):
        if event.button != 1: return
        self.previous()
        self.restart()
        return

    def _on_right_clicked(self, btn, event):
        if event.button != 1: return
        self.next()
        self.restart()
        return

    def stop(self):
        gobject.source_remove(self._fader)
        gobject.source_remove(self._trans_id)
        return

    def start(self):
        self._trans_id = gobject.timeout_add(CAROSEL_TRANSITION_TIMEOUT,
                                             self.transition)
        return

    def restart(self):
        self.stop()
        self.start()
        return

    def next(self):
        self._set_next(fade_in=False)
        return

    def previous(self):
        self._offset -= 2*self.n_posters
        self._set_next(fade_in=False)
        return

    def transition(self, loop=True):
        self._fader = gobject.timeout_add(CAROSEL_FADE_INTERVAL,
                                          self._fade_out)
        return loop

    def set_width(self, width):
        width -=  BORDER_WIDTH_MED
        self._width = width
        self.body.set_size_request(width, -1)
        if not self._show_carosel and self.hbox.get_property('visible'):
            self.show_carosel(False)
            return
        self._remove_all_posters()
        self._build_view(width)
        return

    def show_carosel(self, show_carosel):
        self._show_carosel = show_carosel
        btn = self.show_hide_btn
        if show_carosel:
            btn.set_label(self._hide_label)
            self._build_view(self._width)
            self.back_forward_btn.show()
            self.body.show()
            self.start()
        else:
            self.stop()
            self.back_forward_btn.hide()
            self.hbox.hide()
            self.body.hide()
            self._remove_all_posters()
            btn.set_label(self._show_label)
        return

    def get_carosel_visible(self):
        return self._show_carosel

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return
        cr.save()
        FramedSection.draw(self, cr, a, expose_area)

        # draw footer bg
        #a = self.footer.allocation
        #r = FRAME_CORNER_RADIUS - 1
        #rounded_rectangle_irregular(cr, a.x+1, a.y,
                                    #a.width-2, a.height-1,
                                    #(0, 0, r, r))
        #cr.set_source_rgb(*floats_from_string(COLOR_PURPLE))
        #cr.fill()

        self.more_btn.draw(cr, self.more_btn.allocation, expose_area)

        #self.show_hide_btn.draw(cr, self.show_hide_btn.allocation, expose_area, alpha=0.5)
        fa = self.footer.allocation
        cr.rectangle(fa.x+1, fa.y, fa.width-2, fa.height-1)
        cr.set_source_rgba(*floats_from_string_with_alpha(COLOR_FRAME_HEADER_FILL, 0.3))
        cr.fill()

        self.back_forward_btn.draw(cr, expose_area, alpha=0.5)

        alpha = self._alpha
        layout = self._layout

        if not self.posters:
            cr.restore()
            return

        w = self.posters[0].allocation.width
        layout.set_width((w-self._icon_size-20)*pango.SCALE)

        overlay = self._overlay
        for i, poster in enumerate(self.posters):
            poster.draw(cr, poster.allocation, expose_area,
                        layout, overlay, alpha)

        cr.restore()
        return


class FeaturedPoster(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self, icon_size):
        gtk.EventBox.__init__(self)
        self.set_redraw_on_allocate(False)
        self.set_visible_window(False)
        self.set_size_request(-1, 75)
        self.theme = pathbar_common.PathBarStyle(self)
        self.shape = pathbar_common.SHAPE_RECTANGLE

        self._icon_size = icon_size
        self._icon_pb = None
        self._icon_offset = None
        self._text = None
        self._text_surf = None

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
        return

    def _on_enter(self, poster, event):
        self.set_state(gtk.STATE_PRELIGHT)
        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        return

    def _on_leave(self, poster, event):
        self.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)
        return

    def _on_button_press(self, poster, event):
        if event.button != 1: return
        poster.set_state(gtk.STATE_ACTIVE)
        return

    def _on_button_release(self, poster, event):
        if event.button != 1: return

        region = gtk.gdk.region_rectangle(poster.allocation)
        if not region.point_in(*self.window.get_pointer()[:2]):
            return

        poster.set_state(gtk.STATE_PRELIGHT)

        s = gtk.settings_get_default()
        gobject.timeout_add(s.get_property("gtk-timeout-initial"),
                            self.emit, 'clicked')
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

    def _cache_text_surf(self, layout):
        # text rendering is relatively expensive
        # here a surfaces a cached with the text prerendered
        # makes fade much cheaper to render

        text = self._text

        # render text to surface in black and cache
        color = COLOR_BLACK
        layout.set_markup('<span color="%s">%s</span>' % (color, text))
        w, h = layout.get_pixel_extents()[1][2:]

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)
        pcr = pangocairo.CairoContext(cr)
        pcr.show_layout(layout)

        self._text_surf = surf
        del pcr, cr
        return

    def cache_assets(self, app, layout):
        self.app = app
        self._icon_pb = pb = app[AppStore.COL_ICON]
        self._installed = app[AppStore.COL_INSTALLED]

        # cache markup string and cache pixel extents
        text = app[AppStore.COL_TEXT]
        name, summary = text.splitlines()
        self._text = '%s\n%s' % ((H3 % name), (P_SMALL % summary))

        # set atk stuff
        acc = self.get_accessible()
        acc.set_name(name)
        acc.set_description(summary)

        # cache rendered text
        self._cache_text_surf(layout)

        # calc position of centered pixbuf
        pw, ph = pb.get_width(), pb.get_height() 
        px, py = 0, 3

        ico = self._icon_size
        if pw != ico or ph != ico:
            px = (ico-pw)/2
            py += (ico-ph)/2
        self._icon_offset = px, py
        return

    def draw_ltr(self, cr, a, expose_area, layout, overlay, alpha):
        # draw application icon
        cr.set_source_pixbuf(self._icon_pb, *self._icon_offset)
        cr.paint_with_alpha(alpha)

        # draw installed overlay icon if app is installed
        if self._installed:
            cr.set_source_pixbuf(overlay, 17, 16)
            cr.paint_with_alpha(alpha)

        # draw text
        if alpha < 1.0:
            # if fading, use cached surface, much cheaper to render
            cr.set_source_surface(self._text_surf,
                                  8 + self._icon_size,
                                  POSTER_CORNER_RADIUS)
            cr.paint_with_alpha(alpha)
        else:
            # we paint the layout use the gtk style because its text rendering seems
            # much nicer than the rendering done by pangocairo...
            layout.set_markup('<span color="%s">%s</span>' % (COLOR_BLACK, self._text))
            self.style.paint_layout(self.window,
                                    self.state,
                                    False,
                                    a,          # area
                                    self,
                                    None,
                                    a.x + 8 + self._icon_size,
                                    a.y + 3,
                                    layout)
        return

    def draw_rtl(self, cr, a, expose_area, layout, overlay, alpha):
        # draw application icon
        x, y = self._icon_offset
        cr.set_source_pixbuf(self._icon_pb,
                             a.width - x - self._icon_pb.get_width(),
                             y)
        cr.paint_with_alpha(alpha)

        # draw installed overlay icon if app is installed
        if self._installed:
            cr.set_source_pixbuf(overlay, a.width - 33, 16) # 33 = 17+16
            cr.paint_with_alpha(alpha)

        # draw text
        if alpha < 1.0:
            # if fading, use cached surface, much cheaper to render
            surf = self._text_surfs[self.state]
            cr.set_source_surface(self._text_surf,
                                  6,
                                  3)
            cr.paint_with_alpha(alpha)
        else:
            # we paint the layout use the gtk style because its text rendering seems
            # much nicer than the rendering done by pangocairo...
            layout.set_markup('<span color="%s">%s</span>' % (COLOR_BLACK, self._text))
            self.style.paint_layout(self.window,
                                    self.state,
                                    False,
                                    a,          # area
                                    self,
                                    None,
                                    a.x + 6,
                                    a.y + 3,
                                    layout)
        return

    def draw(self, cr, a, expose_area, layout, overlay, alpha):
        if draw_skip(a, expose_area): return
        if not self.get_property('visible'): return
        cr.save()
        cr.rectangle(a)
        cr.clip()
        cr.translate(a.x, a.y)

        # depending on state set bg colour and draw a rounded rectangle
        if self.state == gtk.STATE_PRELIGHT:
            self.theme.paint_bg(cr, self, 0, 0, a.width, a.height)
        elif self.state == gtk.STATE_ACTIVE:
            self.theme.paint_bg_active_deep(cr, self, 0, 0, a.width, a.height)

        # if has input focus, draw focus box
        if self.has_focus():
            self.style.paint_focus(self.window,
                                   self.state,
                                   (a.x+1, a.y+1, a.width-2, a.height-2),
                                   self,
                                   'button',
                                   a.x+1, a.y+1,
                                   a.width-2, a.height-2)

        # direction sensitive stuff
        if self.get_direction() != gtk.TEXT_DIR_RTL:
            self.draw_ltr(cr, a, expose_area, layout, overlay, alpha)
        else:
            self.draw_rtl(cr, a, expose_area, layout, overlay, alpha)

        cr.restore()
        return


class WelcomeView(FramedSection):

    def __init__(self):
        FramedSection.__init__(self)
        self.set_size_request(-1, 64)
        print dir(glib)
        self.set_label('<big>Welcome back Matthew</big>')
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return
        FramedSection.draw(self, cr, a, expose_area)

        cr.save()

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

    def draw(self, cr, a, expose_area, alpha=1.0):
        if draw_skip(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        self.theme.paint_bg(cr, self, a.x, a.y, a.width-1, a.height, alpha=alpha)
        if self.has_focus():
            a = self.label.allocation
            x, y, w, h = a.x, a.y, a.width, a.height
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x-2, y-1, w+4, h+2),
                                   self,
                                   'button',
                                   x-2, y-1, w+4, h+2)

        cr.restore()
        return


class CategoryButton(PushButton):

    def __init__(self, markup, image=None):
        PushButton.__init__(self, markup, image)
        self.set_border_width(BORDER_WIDTH_MED)
        self.label.set_line_wrap(gtk.WRAP_WORD)
        self.label.set_justify(gtk.JUSTIFY_CENTER)

        # determine size_request width for label
        layout = self.label.get_layout()
        layout.set_width(CAT_BUTTON_FIXED_WIDTH*pango.SCALE)
        lw, lh = layout.get_pixel_extents()[1][2:]   # ink extents width, height
        self.label.set_size_request(lw, -1)

        self.vbox = gtk.VBox(spacing=VSPACING_SMALL)
        h = lh + VSPACING_SMALL + 2*BORDER_WIDTH_MED + 48 # 32 = icon size
        self.vbox.set_size_request(CAT_BUTTON_FIXED_WIDTH, max(h, CAT_BUTTON_MIN_HEIGHT))

        self.add(self.vbox)
        if self.image:
            self.vbox.pack_start(self.image, False)

        self.vbox.pack_start(self.label)
        self.show_all()
        return

    def calc_width(self, realized_widget):
        return CAT_BUTTON_FIXED_WIDTH + 2*self.get_border_width()

    def draw(self, cr, a, expose_area, theme):
        if draw_skip(a, expose_area): return

        cr.save()
        x, y, w, h = a.x, a.y, a.width, a.height
        r = CAT_BUTTON_CORNER_RADIUS
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
        cr.restore()
        return


class BasicButton(PushButton):

    def __init__(self, markup, border_width=BORDER_WIDTH_SMALL):
        PushButton.__init__(self, markup, image=None)
        self._shape_adjust = 0
        self.set_border_width(border_width)

        self.alignment = gtk.Alignment(0.5, 0.5)
        self.alignment.add(self.label)

        self.add(self.alignment)
        self.show_all()
        return

    def calc_width(self):
        pc = self.get_pango_context()
        layout = pango.Layout(pc)
        layout.set_markup(self.label.get_label())
        lw = layout.get_pixel_extents()[1][2]
        return lw + 24 + self._shape_adjust

    def set_border_width(self, width):
        gtk.EventBox.set_border_width(self, width)
        w = self.calc_width()
        self.set_size_request(w, -1)
        return

    def set_label(self, label):
        self.label.set_markup(label)
        w = self.calc_width()
        self.set_size_request(w, -1)
        return

    def set_shape(self, shape):
        self.shape = shape
        if shape == pathbar_common.SHAPE_START_ARROW:
            self._shape_adjust = self.theme['arrow_width']/2
            self.alignment.set(0.3, 0.5, 0, 0)
        w = self.calc_width()
        self.set_size_request(w, -1)
        return

    def use_flat_palatte(self):
        gray = pathbar_common.color_from_string(COLOR_FRAME_LABEL).shade(1.1)
        orange = pathbar_common.color_from_string(COLOR_ORANGE)
        purple = pathbar_common.color_from_string(COLOR_PURPLE)

        self.theme.gradients = {
            gtk.STATE_NORMAL:      (gray, gray),
            gtk.STATE_ACTIVE:      (purple, purple),
            gtk.STATE_SELECTED:    (orange, orange),
            gtk.STATE_PRELIGHT:    (orange, orange),
            gtk.STATE_INSENSITIVE: (self.theme.theme.mid, self.theme.theme.mid)}

        self.theme.dark_line = {
            gtk.STATE_NORMAL:       gray,
            gtk.STATE_ACTIVE:       purple,
            gtk.STATE_PRELIGHT:     orange,
            gtk.STATE_SELECTED:     orange,
            gtk.STATE_INSENSITIVE:  self.theme.theme.mid}

        self.theme.light_line = {
            gtk.STATE_NORMAL:       gray,
            gtk.STATE_ACTIVE:       purple,
            gtk.STATE_PRELIGHT:     orange,
            gtk.STATE_SELECTED:     orange,
            gtk.STATE_INSENSITIVE:  self.theme.theme.mid}
        return


class EngravedLabel(gtk.Label):

    def __init__(self, *args, **kwargs):
        gtk.Label.__init__(self, *args, **kwargs)
        # kinda ugly but i suppress the 'native' drawing of the widget
        self.connect('expose-event', lambda w, e: True)
        return

    def draw(self, cr, a, expose_area):
        if draw_skip(a, expose_area): return

        text = self.get_text()
        markup = '<span color="%s"><b>%s</b></span>'

        layout = self.get_layout()
        layout.set_markup(markup % (COLOR_WHITE, text))
        self.style.paint_layout(self.window,
                                self.state,
                                False,
                                (a.x, a.y, a.width, a.height+1),          # area
                                self,
                                None,
                                a.x,
                                a.y + 1,
                                layout)

        layout.set_markup(markup % (COLOR_FRAME_LABEL, text))
        self.style.paint_layout(self.window,
                                self.state,
                                False,
                                None,          # area
                                self,
                                None,
                                a.x,
                                a.y,
                                layout)
        return


class Test:

    def __init__(self):
        w = gtk.Window()
        w.set_size_request(500, 400)
        w.connect('destroy', gtk.main_quit)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
        w.add(scrolled)

        view = CategoriesViewGtk()
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
