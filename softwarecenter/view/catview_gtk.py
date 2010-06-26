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

# some nice colours
COLOR_ORANGE =  '#F15D22'   # hat tip OMG UBUNTU!
COLOR_PURPLE =  '#4D1F40'   # hat tip OMG UBUNTU!

# MAX_POSTER_COUNT should be a number less than the number of featured apps
CAROUSEL_MAX_POSTER_COUNT =      8
CAROUSEL_MIN_POSTER_COUNT =      1
CAROUSEL_ICON_SIZE =             4*mkit.EM
CAROUSEL_POSTER_MIN_WIDTH =      12*mkit.EM
CAROUSEL_POSTER_MIN_HEIGHT =     min(64, 4*mkit.EM) + 5*mkit.EM
CAROUSEL_TRANSITION_TIMEOUT =    20000 # as per spec this should be 20000 (20 seconds)
CAROUSEL_FADE_INTERVAL =         50 # msec
CAROUSEL_FADE_STEP =             0.05 # value between 0.0 and 1.0

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
        self.vbox = gtk.VBox(spacing=mkit.SPACING_SMALL)
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
        self.featured_carousel = None
        self.newapps_carousel = None
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
        self.connect('style-set', self._on_style_set)
        return

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_departments()
        self._append_featured_and_new()
        return

    def _build_subcat_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments()
        return

    def _append_featured_and_new(self):
        # carousel hbox
        self.hbox_inner = gtk.HBox(spacing=mkit.SPACING_SMALL)
        self.hbox_inner.set_homogeneous(True)

        featured_cat = get_category_by_name(self.categories,
                                            'Featured Applications')    # untranslated name

        # the spec says the carousel icons should be 4em
        # however, by not using a stock icon size, icons sometimes dont
        # look to great.

        # so based on the value of 4*em we try to choose a sane stock
        # icon size
        best_stock_size = mkit.get_nearest_stock_size(CAROUSEL_ICON_SIZE)

        #print featured_cat, featured_cat[0]
        featured_apps = AppStore(self.cache,
                                 self.db,
                                 self.icons,
                                 featured_cat.query,
                                 self.apps_limit,
                                 True,
                                 self.apps_filter,
                                 icon_size=best_stock_size,
                                 global_icon_cache=False)

        self.featured_carousel = CarouselView(featured_apps, _('Featured Applications'))
        self.featured_carousel.more_btn.connect('clicked',
                                  self._on_category_clicked,
                                  featured_cat)
        # pack featured carousel into hbox
        self.hbox_inner.pack_start(self.featured_carousel, False)

        # create new-apps widget
        new_cat = get_category_by_name(self.categories, 'New Applications')
        if new_cat:
            new_apps = AppStore(self.cache,
                                self.db,
                                self.icons,
                                new_cat[0].query,
                                self.apps_limit,
                                True,
                                self.apps_filter,
                                icon_size=CAROUSEL_ICON_SIZE,
                                global_icon_cache=False)

        else:
            new_apps = None

        self.newapps_carousel = CarouselView(new_apps, _("What's New"))
        self.newapps_carousel.more_btn.connect('clicked',
                                           self._on_category_clicked,
                                           new_cat)
        # pack new carousel into hbox
        self.hbox_inner.pack_start(self.newapps_carousel, False)

        # append carousel's to lobby page
        self.vbox.pack_start(self.hbox_inner, False)
        return

    def _append_departments(self):
        # create departments widget
        self.departments = mkit.LayoutView()

        # set the departments section to use the label markup we have just defined
        self.departments.set_label(H2 % self.header)

#        enquirer = xapian.Enquire(self.db.xapiandb)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories[:-1])

        for cat in sorted_cats:
            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

            # sanitize text so its pango friendly...
            name = gobject.markup_escape_text(cat.name.strip())

            cat_btn = CategoryButton(name,
                                     icon_name=cat.iconname,
                                     icon_size=gtk.ICON_SIZE_LARGE_TOOLBAR)

            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # append the departments section to the page
        self.vbox.pack_start(self.departments, False)
        return

    def _append_subcat_departments(self):
        # create departments widget
        if not self.departments:
            self.departments = mkit.LayoutView()
            # append the departments section to the page
            self.vbox.pack_start(self.departments, False)
            self.departments.show_all()
        else:
            self.departments.clear_all()

        # set the departments section to use the label
        header = gobject.markup_escape_text(self.header)
        self.departments.set_label(H2 % header)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories[:-1])

        for cat in sorted_cats:
            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

            # sanitize text so its pango friendly...
            name = gobject.markup_escape_text(cat.name.strip())

            cat_btn = CategoryButton(name,
                                     icon_name=cat.iconname,
                                     icon_size=gtk.ICON_SIZE_LARGE_TOOLBAR)

            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # kinda hacky doing this here...
        best_fit = self._get_best_fit_width()
        self.departments.set_width(best_fit)
        return

    def _full_redraw_cb(self):
        self.queue_draw()
        return False

    def _full_redraw(self):
        # If we relied on a single queue_draw newly exposed (previously
        # clipped) regions of the Viewport are blighted with
        # visual artefacts, so...

        # Two draws are queued; one immediately and one as an idle process

        # The immediate draw results in visual artefacts
        # but without which the resize feels 'laggy'.
        # The idle redraw cleans up the regions affected by 
        # visual artefacts.

        # This all seems to happen fast enough such that the user will
        # not to notice the temporary visual artefacts.  Peace out.

        self.queue_draw()
        gobject.idle_add(self._full_redraw_cb)
        return

    def _get_best_fit_width(self):
        if not self.parent: return 1
        # parent alllocation less the sum of all border widths
        return self.parent.allocation.width - \
                2*(mkit.BORDER_WIDTH_LARGE + mkit.BORDER_WIDTH_MED) - mkit.BORDER_WIDTH_LARGE

    def _on_style_set(self, widget, old_style):
        mkit.update_em_metrics()
        self.queue_draw()
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

    def _on_allocate(self, widget, allocation):
        if self._prev_width != widget.parent.allocation.width:
            self._prev_width = widget.parent.allocation.width
            best_fit = self._get_best_fit_width()

            if self.featured_carousel:
                self.featured_carousel.set_width(best_fit/2)
            if self.newapps_carousel:
                self.newapps_carousel.set_width(best_fit/2)
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

        # draw departments
        self.departments.draw(cr, self.departments.allocation, expose_area)

        if not self.in_subsection:
            # draw featured carousel
            if self.featured_carousel:
                self.featured_carousel.draw(cr,
                                            self.featured_carousel.allocation,
                                            expose_area)
            if self.newapps_carousel:
                self.newapps_carousel.draw(cr,
                                           self.newapps_carousel.allocation,
                                           expose_area)

        del cr
        return

    def _cleanup_poster_sigs(self):
        # clean-up and connect signal handlers
        for sig_id in self._poster_sigs:
            gobject.source_remove(sig_id)
        self._poster_sigs = []
        if self.featured_carousel:
            for poster in self.featured_carousel.posters:
                self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))
        if self.newapps_carousel:
            for poster in self.newapps_carousel.posters:
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


class CategoryButton(mkit.HButton):
    
    def __init__(self, markup, icon_name, icon_size):
        mkit.HButton.__init__(self, markup, icon_name, icon_size)

        self.set_relief(gtk.RELIEF_NONE)
        self.set_has_action_arrow(True)
        self.set_internal_xalignment(0.0)    # basically justify-left
        self.set_internal_spacing(mkit.SPACING_LARGE)
        self.set_border_width(mkit.BORDER_WIDTH_MED)
        return


class CarouselView(mkit.FramedSection):

    def __init__(self, carousel_apps, title):
        mkit.FramedSection.__init__(self)
        self.title = title

        self.hbox = gtk.HBox(spacing=mkit.SPACING_SMALL)
        self.hbox.set_homogeneous(True)
        self.body.pack_start(self.hbox, False)

        #self.play_pause_btn = mkit.PlayPauseButton()
        #self.play_pause_btn.set_shape(mkit.SHAPE_CIRCLE)
        #self.play_pause_btn.set_relief(gtk.RELIEF_NONE)

        self.header.set_spacing(mkit.SPACING_SMALL)

        self.posters = []
        self.n_posters = 0
        self._show_carousel = True

        self.set_redraw_on_allocate(False)
        self.carousel_apps = carousel_apps  # an AppStore

        self.set_label(H2 % title)

        # \xbb == U+00BB == RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
        label = _('All')
        self.more_btn = mkit.HButton('<u>%s</u>' % label)
        self.more_btn.set_relief(gtk.RELIEF_NONE)

        self.header.pack_end(self.more_btn, False)
        #self.header.pack_end(self.play_pause_btn, False)

        if carousel_apps:
            self._icon_size = carousel_apps.icon_size
            self._offset = random.randrange(len(carousel_apps))
            self.connect('realize', self._on_realize)
        else:
            self._icon_size = 48
            self._offset = 0

        self._width = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None

        self.show_all()

       #self.more_btn.connect_after('realize', self._on_more_btn_realize)
        return

    def _on_realize(self, widget):
        #self._cache_overlay_image("software-center-installed")
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

    def _build_view(self, width):
        if not self.carousel_apps: return

        # push the offset back, so when we recache assets do so from the
        # starting point we were at in the previous incarnation
        #self._offset -= self.n_posters

        # number of posters we should have given available space
        n = width / CAROUSEL_POSTER_MIN_WIDTH
        n = (width - n*self.hbox.get_spacing()) / CAROUSEL_POSTER_MIN_WIDTH
        n = max(CAROUSEL_MIN_POSTER_COUNT, n)
        n = min(CAROUSEL_MAX_POSTER_COUNT, n)

        # do nothing if the the new number of posters matches the
        # old number of posters
        if n == self.n_posters:
            return

        # repack appropriate number of new posters (and make sure
        # we do not try to show more than we have)
        
        # if n is smaller than our previous number of posters,
        # then we remove just the right number of posters from the carousel
        if n < self.n_posters:
            n_remove = self.n_posters - n
            self._offset -= n_remove
            for i in range(n_remove):
                poster = self.posters[i]
                # leave no traces remaining (of the poster)
                self.hbox.remove(poster)
                poster.destroy()
                del self.posters[i]

        # if n is greater than our previous number of posters,
        # we need to pack in extra posters
        else:
            n_add = n - self.n_posters
            for i in range(n_add):
                poster = CarouselPoster(icon_pixel_size=self._icon_size)
                self.posters.append(poster)
                self.hbox.pack_start(poster)
                poster.show()

        self.n_posters = n
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
            if self._offset == len(self.carousel_apps):
                self._offset = 0

            app = self.carousel_apps[self._offset]
            poster.set_app(app)
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
        self._offset -= self.n_posters
        self._set_next(fade_in=False)
        return

    def transition(self, loop=True):
        self._fader = gobject.timeout_add(CAROUSEL_FADE_INTERVAL,
                                          self._fade_out)
        return loop

    def set_width(self, width):
        self._width = width
        self.body.set_size_request(width, -1)
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
        if mkit.not_overlapping(a, expose_area): return
        mkit.FramedSection.draw(self, cr, a, expose_area)

        self.more_btn.draw(cr, self.more_btn.allocation, expose_area)
        #self.play_pause_btn.draw(cr, self.play_pause_btn.allocation, expose_area)

        alpha = self._alpha
        layout = self._layout

        if not self.posters: return

        for poster in self.posters:
            # check poster has an app set (when reallocation occurs,
            # new posters miss out on set_app() which only
            # occurs during carousel transistions
            if not poster.app:
                app = self.carousel_apps[self._offset]
                poster.set_app(app)

                self._offset += 1
                if self._offset == len(self.carousel_apps):
                    self._offset = 0

            poster.draw(cr, poster.allocation, expose_area, alpha)
        return


class CarouselPoster(mkit.VButton):

    def __init__(self, markup='none', icon_name='none', \
                 icon_size=gtk.ICON_SIZE_DIALOG, icon_pixel_size=48):

        mkit.VButton.__init__(self, markup, icon_name, icon_size)

        self.set_relief(gtk.RELIEF_NONE)
        self.set_border_width(mkit.BORDER_WIDTH_LARGE)
        self.set_internal_spacing(mkit.SPACING_SMALL)

        self.label.set_justify(gtk.JUSTIFY_CENTER)
        self.image.set_size_request(-1, icon_pixel_size)
        self.box.set_size_request(-1, CAROUSEL_POSTER_MIN_HEIGHT)

        self.app = None

        # we inhibit the native gtk drawing for both the Image and Label
        self.connect('expose-event', lambda w, e: True)
        
        self.connect('size-allocate', self._on_allocate)
        return

    def _on_allocate(self, widget, allocation):
        ia = self.label.allocation  # label allocation
        layout = self.label.get_layout()
        layout.set_width((ia.width+12)*pango.SCALE)
        layout.set_wrap(pango.WRAP_WORD)
        return

    def set_app(self, app):
        self.app = app

        markup = '<b>%s</b>' % app[AppStore.COL_APP_NAME]
        pb = app[AppStore.COL_ICON]

        self.set_label(markup)
        self.image.set_from_pixbuf(pb)
        return

    def draw(self, cr, a, expose_area, alpha=1.0):
        if mkit.not_overlapping(a, expose_area): return
        mkit.VButton.draw(self, cr, a, expose_area, alpha)

        cr.save()
        cr.rectangle(a)
        cr.clip()

        if self.image.get_storage_type() == gtk.IMAGE_PIXBUF:
            pb = self.image.get_pixbuf()
            ia = self.image.allocation

            # paint pixbuf
            cr.set_source_pixbuf(pb,
                                 a.x + (a.width - pb.get_width())/2,
                                 ia.y + (ia.height - pb.get_height())/2)

            cr.paint_with_alpha(alpha)

        la = self.label.allocation  # label allocation
        layout = self.label.get_layout()

        if alpha < 1.0:
            # text colour from gtk.Style
            rgba = mkit.floats_from_gdkcolor_with_alpha(self.style.text[self.state], alpha)

            pcr = pangocairo.CairoContext(cr)
            pcr.save()
            pcr.rectangle(la.x-6, la.y, la.width+12, la.height)
            pcr.clip()
            pcr.move_to(ia.x-6, la.y)
            pcr.set_source_rgba(*rgba)
            pcr.show_layout(layout)
            pcr.restore()
            del pcr
        else:
            self.style.paint_layout(self.window,
                                    self.state,
                                    True,
                                    a,
                                    self,
                                    None,
                                    la.x-6, la.y,
                                    layout)
        cr.restore()
        return


class CarouselNavPoints(gtk.HBox):
    
    def __init__(self):
        gtk.HBox.__init__(self, spacing=HSPACING_XLARGE)
        return

    def set_n_navpoints(self, n_navpoints):
        for i in range(n_navpoints):
            np = VButton(markup=' ')
            np.set_shape(mkit.SHAPE_CIRCLE)
            self.pack_start(np, False)
        return

    def draw(self, cr, a, expose_area):
        return
