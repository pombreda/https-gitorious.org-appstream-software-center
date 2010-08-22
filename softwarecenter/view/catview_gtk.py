import gtk
import atk
import gobject
import cairo
import pango
import pangocairo
import logging
import gettext
import glib
import glob
import locale
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


SHADOW_CACHE = {'n' : cairo.ImageSurface.create_from_png('data/images/rshadow-n.png'),
                'w' : cairo.ImageSurface.create_from_png('data/images/rshadow-w.png'),
                'e' : cairo.ImageSurface.create_from_png('data/images/rshadow-e.png'),
                'bloom96' : cairo.ImageSurface.create_from_png('data/images/bloom96.png')}



# MAX_POSTER_COUNT should be a number less than the number of featured apps
CAROUSEL_MAX_POSTER_COUNT =      8
CAROUSEL_MIN_POSTER_COUNT =      1
CAROUSEL_ICON_SIZE =             4*mkit.EM
#CAROUSEL_POSTER_CORNER_RADIUS =  int(0.8*mkit.EM)    
CAROUSEL_POSTER_MIN_WIDTH =      11*mkit.EM
CAROUSEL_POSTER_MIN_HEIGHT =     min(64, 4*mkit.EM) + 5*mkit.EM
CAROUSEL_PAGING_DOT_SIZE =       max(6, int(0.6*mkit.EM+0.5))

# as per spec transition timeout should be 15000 (15 seconds)
CAROUSEL_TRANSITION_TIMEOUT =    15000

# spec says the fade duration should be 1 second, these values suffice:
CAROUSEL_FADE_INTERVAL =         50 # msec
CAROUSEL_FADE_STEP =             0.1 # value between 0.0 and 1.0

H1 = '<big><b>%s<b></big>'
H2 = '<big>%s</big>'
H3 = '<b>%s</b>'
H4 = '%s'
H5 = '<small><b>%s</b></small>'

P =  '%s'
P_SMALL = '<small>%s</small>'


class CategoriesViewGtk(gtk.Viewport, CategoriesView):

    __gsignals__ = {
        "category-selected" : (gobject.SIGNAL_RUN_LAST,
                               gobject.TYPE_NONE, 
                               (gobject.TYPE_PYOBJECT, ),
                              ),

        "application-activated" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (gobject.TYPE_PYOBJECT, ),
                                  ),
                                  
        "show-category-applist" : (gobject.SIGNAL_RUN_LAST,
                                   gobject.TYPE_NONE,
                                   (),)
        }


    def __init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit=0,
                 root_category=None):

        """ init the widget, takes
        
        datadir - the base directory of the app-store data
        desktopdir - the dir where the applications.menu file can be found
        db - a Database object
        icons - a gtk.IconTheme
        root_category - a Category class with subcategories or None
        """
        
        self.cache = cache
        self.db = db
        self.icons = icons

        self.section_color = mkit.floats_from_string('#0769BC')
        self.section_image = cairo.ImageSurface.create_from_png('data/images/clouds.png')
        self.subsection_image = None

        gtk.Viewport.__init__(self)
        CategoriesView.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        self.vbox = gtk.VBox(spacing=mkit.SPACING_XLARGE)
        self.vbox.set_redraw_on_allocate(False)
        self.vbox.set_border_width(mkit.BORDER_WIDTH_LARGE)
        self.add(self.vbox)

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

    def _build_subcat_view(self, root_category, num_items):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments(root_category, num_items)
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
        best_stock_size = 64#mkit.get_nearest_stock_size(64)
        featured_apps = AppStore(self.cache,
                                 self.db, 
                                 self.icons,
                                 featured_cat.query,
                                 self.apps_limit,
                                 exact=True,
                                 filter=self.apps_filter,
                                 icon_size=best_stock_size,
                                 global_icon_cache=False,
                                 nonapps_visible=False)

        self.featured_carousel = CarouselView(featured_apps, _('Featured'), self.icons)
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
                                new_cat.query,
                                new_cat.item_limit,
                                new_cat.sortmode,
                                self.apps_filter,
                                icon_size=best_stock_size,
                                global_icon_cache=False,
                                nonapps_visible=False)
            self.newapps_carousel = CarouselView(
                new_apps, _("What's New"), self.icons, start_random=False)
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
        self.departments.header_alignment.set_padding(3, 6, 0, 0)

        # set the departments section to use the label markup we have just defined
        self.departments.set_label(H2 % self.header)

#        enquirer = xapian.Enquire(self.db.xapiandb)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        for cat in sorted_cats:
            if cat.untranslated_name not in ('Featured Applications',
                                             'New Applications'):
                #enquirer.set_query(cat.query)
                ## limiting the size here does not make it faster
                #matches = enquirer.get_mset(0, len(self.db))
                #estimate = matches.get_matches_estimated()

                # sanitize text so its pango friendly...
                name = gobject.markup_escape_text(cat.name.strip())

                cat_btn = CategoryButton(name, cat.iconname, self.icons)
                cat_btn.connect('clicked', self._on_category_clicked, cat)
                # append the department to the departments widget
                self.departments.append(cat_btn)

        # append the departments section to the page
        self.vbox.pack_start(self.departments, False)
        return
        
    def _append_subcat_departments(self, root_category, num_items):
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
        sorted_cats = categories_sorted_by_name(self.categories)

        for cat in sorted_cats:
            #enquirer.set_query(cat.query)
            ## limiting the size here does not make it faster
            #matches = enquirer.get_mset(0, len(self.db))
            #estimate = matches.get_matches_estimated()

            # sanitize text so its pango friendly...
            name = gobject.markup_escape_text(cat.name.strip())

            cat_btn = SubcategoryButton(name, cat.iconname, self.icons)

            cat_btn.connect('clicked', self._on_category_clicked, cat)
            # append the department to the departments widget
            self.departments.append(cat_btn)

        # append an additional button to show all of the items in the category
        name = gobject.markup_escape_text(_("All %s") % num_items)
        show_all_btn = SubcategoryButton(name, "category-show-all", self.icons)
        all_cat = Category("All", _("All"), "category-show-all", root_category.query)
        show_all_btn.connect('clicked', self._on_category_clicked, all_cat)
        self.departments.append(show_all_btn)

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
        return self.parent.allocation.width - 4*mkit.BORDER_WIDTH_LARGE

    def _on_style_set(self, widget, old_style):
        mkit.update_em_metrics()
        self.queue_draw()
        return

    def _on_app_clicked(self, btn):
        app = btn.app
        appname = app[AppStore.COL_APP_NAME]
        pkgname = app[AppStore.COL_PKGNAME]
        popcon = app[AppStore.COL_POPCON]
        self.emit("application-activated", Application(appname, pkgname, "", popcon))
        return False

    def _on_category_clicked(self, cat_btn, cat):
        """emit the category-selected signal when a category was clicked"""
        self._logger.debug("on_category_changed: %s" % cat.name)
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
                self.departments.set_width(best_fit)

            # cleanup any signals, its ok if there are none
            self._cleanup_poster_sigs()

        self._full_redraw()   #  ewww
        return

    def _on_expose(self, widget, event):
        # context setup
        expose_area = event.area
        cr = widget.window.cairo_create()
        cr.rectangle(expose_area)
        cr.clip_preserve()

        # base color
        cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.base[self.state]))
        cr.fill()

        # sky
        r,g,b = self.section_color
        lin = cairo.LinearGradient(0,0,0,150)
        lin.add_color_stop_rgba(0, r,g,b, 0.3)
        lin.add_color_stop_rgba(1, r,g,b,0)
        cr.set_source(lin)
        cr.rectangle(0,0,
                     widget.allocation.width, 150)
        cr.fill()

        # clouds

        # subsection
        if isinstance(self.subsection_image, gtk.gdk.Pixbuf):
            w = self.subsection_image.get_width()
            h = self.subsection_image.get_height()
            cr.set_source_pixbuf(self.subsection_image, widget.allocation.width-w, 0)
            cr.paint_with_alpha(0.4)
        elif isinstance(self.section_image, cairo.ImageSurface):
            w = self.section_image.get_width()
            cr.set_source_surface(self.section_image, widget.allocation.width-w, 0)
            cr.paint()

        if self.in_subsection: return

        ## draw carousels
        #r,g,b = mkit.floats_from_string('#F27B4A')
        r,g,b = mkit.floats_from_string('#FFA500')
        #r,g,b = mkit.floats_from_string('#FF0000')

        ca = self.hbox_inner.allocation
        lin = cairo.LinearGradient(ca.x, ca.y+80, ca.x, ca.y+ca.height)
        lin.add_color_stop_rgba(0,0,0,0,1)
        lin.add_color_stop_rgba(1,0,0,0,0)
        cr.mask(lin)

        #rr = mkit.ShapeRoundedRectangle()
        shad = SHADOW_CACHE['w']
        cr.set_source_surface(shad, ca.x-7, ca.y-5)
        #cr.paint()
        cr.mask(lin)
        shad = SHADOW_CACHE['e']
        cr.set_source_surface(shad, ca.x+ca.width-34, ca.y-5)
        cr.mask(lin)

        shad = SHADOW_CACHE['n']
        cr.save()
        w = shad.get_width()
        xo = 0
        cr.rectangle(ca.x+34, ca.y-5, ca.width-68, shad.get_height())
        cr.clip()
        for i in range(ca.width/w + 1):
            cr.set_source_surface(shad, ca.x+34+xo, ca.y-5)
            cr.paint()
            xo+=w

        cr.restore()

        #lin = cairo.LinearGradient(ca.x, ca.y, ca.x, ca.y+ca.height)
        #lin.add_color_stop_rgba(0, r,g,b, 0.12)
        #lin.add_color_stop_rgba(0.52, r,g,b, 0.02)
        #lin.add_color_stop_rgba(1, r,g,b, 0.12)
        #cr.set_source(lin)
        #rr.layout(cr, ca.x, ca.y, ca.x+ca.width, ca.y+ca.height, radius=3)
        ##cr.rectangle(ca)
        #cr.fill()

        ## outline
        #cr.save()
        #cr.translate(0.5,0.5)
        ##cr.rectangle(ca)
        #rr.layout(cr, ca.x, ca.y, ca.x+ca.width, ca.y+ca.height, radius=3)
        #cr.set_line_width(1)
        #cr.set_source_rgb(r,g,b)
        ##cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.mid[self.state]))
        #cr.stroke()

        ## inline
        #rr.layout(cr, ca.x+1, ca.y+1, ca.x+ca.width-1, ca.y+ca.height-1, radius=2.5)
        #cr.set_source_rgba(1,1,1,0.85)
        #cr.stroke()

        ## midline
        cr.save()
        #cr.rectangle(ca.x+1, ca.y-1, ca.width, ca.height)

        rr = mkit.ShapeRoundedRectangle()
        rr.layout(cr, ca.x, ca.y, ca.x+ca.width, ca.y+ca.height, radius=4.5)
        cr.clip_preserve()
        cr.set_source_rgba(r,g,b,0.3)
        cr.mask(lin)

        cr.set_source_rgba(1,1,1,0.5)
        cr.stroke()

        cairo.Context.reset_clip(cr)
        cr.rectangle(ca.x+ca.width/2-1, ca.y+1, 1, ca.height)
        cr.clip()
        cr.set_source_rgba(1,1,1,0.2)
        cr.mask(lin)

        cairo.Context.reset_clip(cr)
        cr.rectangle(ca.x+ca.width/2, ca.y, 1, ca.height)
        cr.clip()
        cr.set_source_rgba(0,0,0,0.2)
        cr.mask(lin)

        cairo.Context.reset_clip(cr)
        cr.rectangle(ca.x+ca.width/2+1, ca.y+1, 1, ca.height)
        cr.clip()
        cr.set_source_rgba(1,1,1,0.2)
        cr.mask(lin)
        cr.restore()



        # draw departments
        self.departments.draw(cr, self.departments.allocation, expose_area)

        # draw featured carousel
        self.featured_carousel.draw(cr,
                                        self.featured_carousel.allocation,
                                        expose_area)
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
        
    def _on_show_all_clicked(self, show_all_btn):
        self.emit("show-category-applist")

    def start_carousels(self):
        self.featured_carousel.start()
        return

    def stop_carousels(self):
        self.featured_carousel.stop()
        return

    def set_subcategory(self, root_category, num_items=0, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name

        ico_inf = self.icons.lookup_icon(root_category.iconname, 150, 0)
        self.categories = root_category.subcategories
        self._build_subcat_view(root_category, num_items)
        return

    def set_section_color(self, color):
        self.section_color = color
        return

    def set_section_image(self, image):
        self.section_image = image
        return


class CarouselView(mkit.FramedSection):

    def __init__(self, carousel_apps, title, icons, start_random=True):
        mkit.FramedSection.__init__(self)

        #self.label.set_etching_rgba(1,1,1,1)

        self.icons = icons

        self.hbox = gtk.HBox(spacing=mkit.SPACING_SMALL)
        self.hbox.set_homogeneous(True)
        self.body.pack_start(self.hbox, False)
        self.page_sel = PageSelector()
        self.body.pack_end(self.page_sel, False,
                           padding=mkit.SPACING_SMALL)

        self.header.set_spacing(mkit.SPACING_SMALL)

        self.title = title
        self.posters = []
        self.n_posters = 0
        self._show_carousel = True

        self.set_redraw_on_allocate(False)
        self.carousel_apps = carousel_apps  # an AppStore

        self.set_label(H2 % title)

        label = _('All')
        self.more_btn = mkit.HLinkButton(label)
        self.more_btn.set_underline(True)
        self.more_btn.set_subdued(True)

        self.header.pack_end(self.more_btn, False)

        if carousel_apps and len(carousel_apps) > 0:
            self._icon_size = carousel_apps.icon_size
            if start_random:
                self._offset = random.randrange(len(carousel_apps))
            else:
                self._offset = 0
            #self.connect('realize', self._on_realize)
        else:
            self._icon_size = 48
            self._offset = 0

        self._is_playing = False
        self._width = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None

        self.show_all()

        self.page_sel.connect('page-selected', self._on_page_selected)
        self.connect('style-set', self._on_style_set)
        return

    def _on_style_set(self, widget, old_style):
        self.more_btn.label.realize()
        self.more_btn.label.modify_text(gtk.STATE_NORMAL, self.style.dark[gtk.STATE_NORMAL])
        return

    def _on_page_selected(self, page_sel, page):
        self.stop()
        self._offset = page*self.n_posters
        self._update_poster_content()
        self._alpha = 1.0
        self.queue_draw()
        self.start()
        return

    #def _cache_overlay_image(self, overlay_icon_name, overlay_size=16):
        #icons = gtk.icon_theme_get_default()
        #try:
            #self._overlay = icons.load_icon(overlay_icon_name,
                                            #overlay_size, 0)
        #except glib.GError:
            ## icon not present in theme, probably because running uninstalled
            #self._overlay = icons.load_icon('emblem-system',
                                            #overlay_size, 0)
        #return

    def _build_view(self, width):
        if not self.carousel_apps or len(self.carousel_apps) == 0:
            return

        # number of posters we should have given available space
        n = width / CAROUSEL_POSTER_MIN_WIDTH
        n = (width - n*self.hbox.get_spacing()) / CAROUSEL_POSTER_MIN_WIDTH
        n = max(CAROUSEL_MIN_POSTER_COUNT, n)
        n = min(CAROUSEL_MAX_POSTER_COUNT, n)

        # do nothing if the the new number of posters matches the
        # old number of posters
        if n == self.n_posters: return

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
                poster = CarouselPoster(icon_size=self._icon_size,
                                        icons=self.icons)
                self.posters.append(poster)
                self.hbox.pack_start(poster)
                poster.show()

        # set how many PagingDot's the PageSelector should display
        pages = float(len(self.carousel_apps)) / n
        #print "pages: ", pages
        if pages - int(pages) > 0.0:
            pages += 1

        #print len(self.carousel_apps), n, pages
        self.page_sel.set_n_pages(int(pages))
        self.n_posters = n

        self._update_pagesel()
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

    def _update_pagesel(self):
        # set the PageSelector page
        if self._offset >= len(self.carousel_apps):
            self._offset = 0
#        print 'BW:', width, self.page_sel.allocation.width
        page = self._offset / self.n_posters
        self.page_sel.set_selected_page(int(page))
        return

    def _update_poster_content(self):
        # update poster content and increment offset
        for poster in self.posters:
            if self._offset == len(self.carousel_apps):
                self._offset = 0

            app = self.carousel_apps[self._offset]
            poster.set_application(app)
            self._offset += 1
        return

    def _set_next(self, fade_in=True):
        self._update_pagesel()
        self._update_poster_content()

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
        if not self._is_playing: return
        self._alpha = 1.0
        self._is_playing = False
        if self._fader:
            gobject.source_remove(self._fader)
        if self._trans_id:
            gobject.source_remove(self._trans_id)
        return

    def start(self):
        if self._is_playing: return
        self._is_playing = True
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
        self.page_sel.set_width(width)
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

        if not self.carousel_apps: return
        alpha = self._alpha

        for poster in self.posters:
            # check that posters have an app set
            # (since when reallocation occurs, new posters miss out on 
            # set_application() which only occurs during carousel
            # transistions) ...
            if not poster.app:
                app = self.carousel_apps[self._offset]
                poster.set_application(app)

                self._offset += 1
                if self._offset == len(self.carousel_apps):
                    self._offset = 0

            poster.draw(cr, poster.allocation, expose_area, alpha)

        self.page_sel.draw(cr, self.page_sel.allocation, expose_area, alpha)
        return


class CategoryButton(mkit.HLinkButton):

    ICON_SIZE = 24

    def __init__(self, markup, icon_name, icons):
        #markup = '<span size="%s">%s</span>' % (mkit.EM*pango.SCALE, markup)
        mkit.HLinkButton.__init__(self, markup, icon_name, self.ICON_SIZE, icons)

        self.set_internal_xalignment(0.0)    # basically justify-left
        self.set_internal_spacing(mkit.SPACING_LARGE)
        self.set_border_width(mkit.BORDER_WIDTH_SMALL)
        return


class SubcategoryButton(mkit.VLinkButton):

    ICON_SIZE = 48

    def __init__(self, markup, icon_name, icons):
        mkit.VLinkButton.__init__(self, markup, icon_name, self.ICON_SIZE, icons)
        self.set_border_width(mkit.BORDER_WIDTH_MED)
        return


class CarouselPoster(mkit.VLinkButton):

    def __init__(self, markup='None', icon_name='None', icon_size=48, icons=None):
        mkit.VLinkButton.__init__(self, markup, icon_name, icon_size, icons)

        self.set_border_width(mkit.BORDER_WIDTH_LARGE)
        self.set_internal_spacing(mkit.SPACING_SMALL)

        self.label.set_justify(gtk.JUSTIFY_CENTER)
        self.image.set_size_request(icon_size, icon_size)
        self.box.set_size_request(-1, CAROUSEL_POSTER_MIN_HEIGHT)

        self.app = None

        # we inhibit the native gtk drawing for both the Image and Label
        self.connect('expose-event', lambda w, e: True)
        self.connect('size-allocate', self._on_allocate)

        # a11y for poster
#        self.set_property("can-focus", True)
        self.a11y = self.get_accessible()
        return

    def _on_allocate(self, widget, allocation):
        ia = self.label.allocation  # label allocation
        layout = self.label.get_layout()
        layout.set_width(ia.width*pango.SCALE)
        layout.set_wrap(pango.WRAP_WORD)
        return

    def set_application(self, app):
        self.app = app

        name = app[AppStore.COL_APP_NAME] or app[AppStore.COL_PKGNAME]

        markup = '%s' % (name)
        pb = app[AppStore.COL_ICON]

        self.set_label(markup)
        self.set_image_from_pixbuf(pb)

        # set a11y text
        self.a11y.set_name(name)

        if not self.image.window:
            self.box.pack_start(self.image, False)
            self.image.show()
        return

    def draw(self, cr, a, expose_area, alpha=1.0):
        if mkit.not_overlapping(a, expose_area): return

        cr.save()
        cr.rectangle(a)
        cr.clip()

        self.alpha = alpha
        self._on_image_expose(self.image, gtk.gdk.Event(gtk.gdk.EXPOSE))

        la = self.label.allocation  # label allocation
        ia = self.image.allocation
        layout = self.label.get_layout()

        if alpha < 1.0:
            # text colour from gtk.Style
            rgba = mkit.floats_from_gdkcolor_with_alpha(self.style.text[self.state], alpha)

            pcr = pangocairo.CairoContext(cr)
            pcr.save()
            pcr.move_to(ia.x, la.y)
            pcr.set_source_rgba(*rgba)
            pcr.layout_path(layout)
            pcr.fill()
            pcr.restore()
            del pcr
        else:
            pcr = pangocairo.CairoContext(cr)
            pcr.save()
            pcr.move_to(ia.x, la.y+1)
            pcr.set_source_rgba(1,1,1,0.85)
            pcr.layout_path(layout)
            pcr.fill()
            pcr.restore()
            del pcr

            self.style.paint_layout(self.window,
                                    self.state,
                                    True,
                                    a,
                                    self,
                                    None,
                                    la.x, la.y,
                                    layout)
        cr.restore()

        # custom focus draw
        if self.has_focus():
            a = self.label.allocation
            #x, y, w, h = a.x, a.y, a.width, a.height
            x, y, w, h = layout.get_pixel_extents()[1] 
            x += a.x
            y += a.y
            self.style.paint_focus(self.window,
                                   self.state,
                                   (x-2, y-1, w+4, h+2),
                                   self,
                                   'expander',
                                   x-2, y-1, w+4, h+2)
        return


class PageSelector(gtk.Alignment):

    __gsignals__ = {
        "page-selected" : (gobject.SIGNAL_RUN_LAST,
                           gobject.TYPE_NONE, 
                           (int,),)
        }

    def __init__(self):
        gtk.Alignment.__init__(self, 0.5, 0.5)
        #self.set_size_request(-1, 2*CAROUSEL_PAGING_DOT_SIZE)
        self.vbox = gtk.VBox(spacing=mkit.SPACING_MED)
        self.add(self.vbox)
        self.show_all()

        self.n_pages = 0
        self.selected = None

        self.dots = []
        self._width = 0
        self._signals = []
        return

    def _on_dot_clicked(self, dot):
        self.emit('page-selected', dot.page_number)
        dot.is_selected = True
        if self.selected:
            self.selected.is_selected = False
            self.selected.queue_draw()
        self.selected = dot
        return

    def _destroy_all_children(self, widget):
        children = widget.get_children()
        if not children: return

        for child in children:
            self._destroy_all_children(child)
            child.destroy()
        return

    def clear_paging_dots(self):
        # remove all dots and clear dot signal handlers
        self._destroy_all_children(self.vbox)

        for sig in self._signals:
            gobject.source_remove(sig)

        self.dots = []
        self._signals = []
        return

    def set_width(self, width):
        self._width = width
        return

    def set_n_pages(self, n_pages):
        self.n_pages = n_pages
        self.clear_paging_dots()

        rowbox = gtk.HBox(spacing=mkit.SPACING_MED)
        row = gtk.Alignment(0.5, 0.5)
        row.add(rowbox)

        self.vbox.pack_start(row)

        max_w = self._width
        #print max_w, self.vbox.allocation.width
        w = 0
        for i in range(int(n_pages)):
            w += CAROUSEL_PAGING_DOT_SIZE + mkit.SPACING_MED

            if w > max_w:
                rowbox = gtk.HBox(spacing=mkit.SPACING_MED)
                row = gtk.Alignment(0.5, 0.5)
                row.add(rowbox)

                self.vbox.pack_start(row, expand=True)
                w = CAROUSEL_PAGING_DOT_SIZE + mkit.SPACING_MED

            dot = PagingDot(i)
            rowbox.pack_start(dot, False)
            self.dots.append(dot)
            self._signals.append(dot.connect('clicked', self._on_dot_clicked))

        self.vbox.show_all()
        return

    def get_n_pages(self):
        return self.n_pages

    def set_selected_page(self, page_n):
        dot = self.dots[page_n]
        dot.is_selected = True

        if self.selected:
            self.selected.is_selected = False
            self.selected.queue_draw()

        self.selected = dot
        dot.queue_draw()
        return

    def draw(self, cr, a, expose_area, alpha):
        if mkit.not_overlapping(a, expose_area): return

        for dot in self.dots:
            dot.draw(cr, dot.allocation, expose_area, alpha)
        return


class PagingDot(mkit.LinkButton):

    def __init__(self, page_number):
        mkit.LinkButton.__init__(self, None, None, None)
        self.set_size_request(-1, CAROUSEL_PAGING_DOT_SIZE)
        self.is_selected = False
        self.page_number = page_number

        # a11y for page selector
        self.set_property("can-focus", True)
        self.a11y = self.get_accessible()
        self.a11y.set_name("Go to page " + str(self.page_number + 1))
        return

    def calc_width(self):
        return CAROUSEL_PAGING_DOT_SIZE

    def draw(self, cr, a, expose_area, alpha):
        cr.save()
        #cr.rectangle(a)
        #cr.clip()
        r,g,b = mkit.floats_from_gdkcolor(self.style.dark[self.state])

        
        cr.save()
        cr.translate(0.5,0.5)
        cr.set_line_width(1)
        c = mkit.ShapeCircle()
        c.layout(cr, a.x, a.y, a.width, a.height)

        if self.is_selected:
            if self.state == gtk.STATE_PRELIGHT or self.has_focus():
                r,g,b = mkit.floats_from_gdkcolor(self.style.dark[gtk.STATE_SELECTED])

            cr.set_source_rgba(r,g,b,alpha)
            cr.fill_preserve()
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_PRELIGHT or self.has_focus():
            r,g,b = mkit.floats_from_gdkcolor(self.style.dark[gtk.STATE_SELECTED])
            cr.set_source_rgba(r,g,b,0.5)
            cr.fill_preserve()
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_NORMAL:
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_ACTIVE:
            cr.set_source_rgb(r,g,b)
            cr.fill_preserve()
            cr.stroke()

        cr.restore()
        return
