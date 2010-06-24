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
import random
import os
import xapian

from widgets import mkit
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

COLOR_ORANGE =  '#F15D22'   # hat tip OMG UBUNTU!
COLOR_PURPLE =  '#4D1F40'   # hat tip OMG UBUNTU!

CAT_BUTTON_FIXED_WIDTH =    108
CAT_BUTTON_MIN_HEIGHT =     96
CAT_BUTTON_BORDER_WIDTH =   6
CAT_BUTTON_CORNER_RADIUS =  8

# MAX_POSTER_COUNT should be a number less than the number of featured apps
CAROUSEL_MAX_POSTER_COUNT =      8
CAROUSEL_MIN_POSTER_COUNT =      1
CAROUSEL_POSTER_MIN_WIDTH =      200 # this is actually more of an approximate minima
CAROUSEL_TRANSITION_TIMEOUT =    20000 # n_seconds * 1000
CAROUSEL_FADE_INTERVAL =         50 # msec  
CAROUSEL_FADE_STEP =             0.2 # value between 0.0 and 1.0

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
                                  ),
                                  
        "show-category-items" : (gobject.SIGNAL_RUN_LAST,
                                 gobject.TYPE_NONE,
                                 (),)
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
        self.vbox = gtk.VBox(spacing=mkit.VSPACING_SMALL)
        self.vbox.set_border_width(mkit.BORDER_WIDTH_LARGE)

        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)
        viewport.add(self.vbox)
        self.add(viewport)
        self.vbox.set_redraw_on_allocate(False)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # append sections
        self.carousel = None
        self.carousel_new = None
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
        self._append_departments()
        self._append_featured_and_new()
        return

    def _build_subcat_view(self, root_category, num_items):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        # create departments widget
        if not self.departments:
            self.departments = mkit.LayoutView()
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
            # finally, create the department with label markup and icon
            cat_btn = mkit.VButton(name, 
                                   icon_name=cat.iconname,
                                   icon_size= gtk.ICON_SIZE_DIALOG)
            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # TODO:  remove the ">>" once we have the correct icon to use
        #        in the show_all_button (for now, just show the category icon)
        name = _("All %s >>") % num_items
        fixed_name = gobject.markup_escape_text(name)
        show_all_btn = mkit.VButton(fixed_name, 
                                    icon_name=root_category.iconname,
                                    icon_size= gtk.ICON_SIZE_DIALOG)
        # show_all_btn.connect('clicked', self._on_show_all_clicked, root_category)
        show_all_btn.connect('clicked', self._on_show_all_clicked)
        # append as the last item in the departments list
        self.departments.append(show_all_btn)

        # kinda hacky doing this here...
        best_fit = self._get_layout_best_fit_width()
        self.departments.set_width(best_fit)
        return

    def _append_featured_and_new(self):
        featured_cat = get_category_by_name(self.categories,
                                            'Featured Applications')    # untranslated name
        featured_apps = AppStore(self.cache,
                                 self.db,
                                 self.icons,
                                 featured_cat.query,
                                 self.apps_limit,
                                 True,
                                 self.apps_filter)

        carousel = FeaturedView(featured_apps, _("Featured Applications"))
        carousel.more_btn.connect('clicked',
                                 self._on_category_clicked,
                                 featured_cat)
 
        self.carousel = carousel

        # create new-apps widget
        new_cat = get_category_by_name(self.categories, 'New Applications')
        new_apps = AppStore(self.cache,
                            self.db,
                            self.icons,
                            new_cat.query,
                            self.apps_limit,
                            True,
                            self.apps_filter)
        self.carousel_new = FeaturedView(new_apps, _("What's New"))
        self.carousel_new.more_btn.connect('clicked',
                                           self._on_category_clicked,
                                           new_cat)
 
        # put in the box
        self.hbox_inner = gtk.HBox(spacing=mkit.HSPACING_SMALL)
        self.hbox_inner.set_homogeneous(True)
        self.hbox_inner.pack_start(self.carousel, False)
        self.hbox_inner.pack_start(self.carousel_new, False)
        self.vbox.pack_start(self.hbox_inner, False)
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
        self.departments = mkit.LayoutView()

        # set the departments section to use the label markup we have just defined
        self.departments.set_label(H2 % self.header)

#        enquirer = xapian.Enquire(self.db.xapiandb)

        for cat in self.categories[:-1]:
            # make sure the string is parsable by pango, i.e. no funny characters
            name = gobject.markup_escape_text(cat.name.strip())

            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

            cat_btn = mkit.VButton(name,
                                   icon_name=cat.iconname,
                                   icon_size=gtk.ICON_SIZE_DIALOG)

            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # append the departments section to the page
        self.vbox.pack_start(self.departments, False)
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

    def _on_show_hide_carousel_clicked(self, btn, carousel):
        carousel_visible = self.carousel.get_carousel_visible()
        if carousel_visible:
            carousel.show_carousel(False)
        else:
            carousel.show_carousel(True)
            self._cleanup_poster_sigs()

        self._full_redraw()
        return

    def _get_layout_best_fit_width(self):
        if not self.parent: return 1
        # parent alllocation less the sum of all border widths
        return self.parent.allocation.width - \
                2*mkit.BORDER_WIDTH_LARGE - 2*mkit.BORDER_WIDTH_MED

    def _on_allocate(self, widget, allocation):
        if self._prev_width != widget.parent.allocation.width:
            self._prev_width = widget.parent.allocation.width
            best_fit = self._get_layout_best_fit_width()

            if self.carousel:
                self.carousel.set_width(best_fit/2)
            if self.carousel_new:
                self.carousel_new.set_width(best_fit/2)
            if self.departments:
                self.departments.clear_rows()
                self.departments.set_width(best_fit)
            # cleanup any signals, its ok if there are none
            self._cleanup_poster_sigs()

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip()
        #cr.clip_preserve()

        #cr.set_source_rgb(*floats_from_string(COLOR_FRAME_BG_FILL))
        #cr.fill()

        # draw departments
        self.departments.draw(cr, self.departments.allocation, expose_area)

        if not self.in_subsection:
            # draw featured carousel
            self.carousel.draw(cr, self.carousel.allocation, expose_area)
            self.carousel_new.draw(cr, self.carousel_new.allocation, expose_area)

        del cr
        return

    def _cleanup_poster_sigs(self):
        # clean-up and connect signal handlers
        for sig_id in self._poster_sigs:
            gobject.source_remove(sig_id)
        self._poster_sigs = []
        if self.carousel:
            for poster in self.carousel.posters:
                self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))
        if self.carousel_new:
            for poster in self.carousel_new.posters:
                self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))
        return

    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name))
        
    def _on_show_all_clicked(self, show_all_btn):
        self.emit("show-category-items")

    def set_subcategory(self, root_category, num_items=0, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name
        self.categories = root_category.subcategories
        self._build_subcat_view(root_category, num_items)
        return

class FeaturedView(mkit.FramedSection):

    def __init__(self, featured_apps, title):
        mkit.FramedSection.__init__(self)
        self.title = title

        self.hbox = gtk.HBox(spacing=mkit.HSPACING_SMALL)
        self.hbox.set_homogeneous(True)
        self.body.pack_start(self.hbox, False)

        self.play_pause_btn = mkit.PlayPauseButton()
        self.play_pause_btn.set_shape(mkit.SHAPE_CIRCLE)

        self.header.set_spacing(mkit.HSPACING_SMALL)

        self.posters = []
        self.n_posters = 0
        self._show_carousel = True

        self.set_redraw_on_allocate(False)
        self.featured_apps = featured_apps

        self.set_label(H2 % title)

        # \xbb == U+00BB == RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        label = _(u'View all \xbb')
        self.more_btn = mkit.HButton('<small>%s</small>' % label)
        self.header.pack_end(self.more_btn, False)
        self.header.pack_end(self.play_pause_btn, False)

        self._width = 0
        self._icon_size = self.featured_apps.icon_size
        if len(featured_apps):
            self._offset = random.randrange(len(featured_apps))
        else:
            self._offset = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None

        self.show_all()

        self.connect('realize', self._on_realize)
        self.more_btn.connect_after('realize', self._on_more_btn_realize)
        return

    def _on_realize(self, widget):
        # cache a pango layout for text ops and overlay image for installed apps
        self._cache_layout()
        self._cache_overlay_image("software-center-installed")
        # init asset cache for each poster
        self._set_next()
        # start the carousel
        self.start()
        return

    def _on_more_btn_realize(self, widget):
        # set the play pause size, relative to the height of the 'more' button
        h = self.more_btn.allocation.height
        self.play_pause_btn.set_size_request(h, h)
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
        n = width / CAROUSEL_POSTER_MIN_WIDTH
        n = max(CAROUSEL_MIN_POSTER_COUNT, n)
        n = min(CAROUSEL_MAX_POSTER_COUNT, n)
        self.n_posters = n    

        # repack appropriate number of new posters (and make sure
        # we do not try to show more than we have)
        for i in range(min(n, len(self.featured_apps))):
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
        self._alpha += CAROUSEL_FADE_STEP
        if self._alpha >= 1.0:
            self._alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _fade_out(self):
        self._alpha -= CAROUSEL_FADE_STEP
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
            self._fader = gobject.timeout_add(CAROUSEL_FADE_INTERVAL,
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
        self._trans_id = gobject.timeout_add(CAROUSEL_TRANSITION_TIMEOUT,
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
        self._fader = gobject.timeout_add(CAROUSEL_FADE_INTERVAL,
                                          self._fade_out)
        return loop

    def set_width(self, width):
        width -=  mkit.BORDER_WIDTH_MED
        self._width = width
        self.body.set_size_request(width, -1)
        if not self._show_carousel and self.hbox.get_property('visible'):
            self.show_carousel(False)
            return
        self._remove_all_posters()
        self._build_view(width)
        return

    def show_carousel(self, show_carousel):
        self._show_carousel = show_carousel
        btn = self.show_hide_btn
        if show_carousel:
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

    def get_carousel_visible(self):
        return self._show_carousel

    def draw(self, cr, a, expose_area):
        if mkit.is_overlapping(a, expose_area): return
        mkit.FramedSection.draw(self, cr, a, expose_area)

        if self.more_btn.state == gtk.STATE_NORMAL:
            self.more_btn.draw(cr, self.more_btn.allocation, expose_area, alpha=0.4)
        else:
            self.more_btn.draw(cr, self.more_btn.allocation, expose_area)

        if self.play_pause_btn.state == gtk.STATE_NORMAL:
            self.play_pause_btn.draw(cr, self.play_pause_btn.allocation, expose_area, alpha=0.4)
        else:
            self.play_pause_btn.draw(cr, self.play_pause_btn.allocation, expose_area)

        alpha = self._alpha
        layout = self._layout

        if not self.posters:
            #cr.restore()
            return

        overlay = self._overlay
        for i, poster in enumerate(self.posters):
            poster.draw(cr, poster.allocation, expose_area,
                        layout, overlay, alpha)
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

        self.theme = mkit.Style(self)
        self.shape = mkit.SHAPE_RECTANGLE

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

        # we only want to cache a text surf when the poster
        # has been allocated so we get correct line wrapping.
        if self.allocation.width == 1: return
        text = self._text

        # render text to surface in black and cache
        layout.set_width((self.allocation.width - 32 - 20)*pango.SCALE)
        layout.set_wrap(pango.WRAP_WORD_CHAR)
        layout.set_markup(text)
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
            if not self._text_surf: self._cache_text_surf(layout)

            cr.set_source_surface(self._text_surf,
                                  8 + self._icon_size,
                                  POSTER_CORNER_RADIUS)
            cr.paint_with_alpha(alpha)
        else:
            # we paint the layout use the gtk style because its text rendering seems
            # much nicer than the rendering done by pangocairo...
            layout.set_markup(self._text)
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
            layout.set_markup(self._text)
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
        if mkit.is_overlapping(a, expose_area): return
        if not self.get_property('visible'): return

        layout.set_width((self.allocation.width - 32 - 20)*pango.SCALE)

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
