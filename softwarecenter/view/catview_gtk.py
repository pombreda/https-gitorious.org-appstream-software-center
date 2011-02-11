import gtk
import gobject
import cairo
import pango
import pangocairo
import gettext
import glib
import random
import os
import xapian

from gettext import gettext as _

from widgets import mkit
from appview import AppStore
from softwarecenter.db.database import Application
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.backend.zeitgeist_simple import zeitgeist_singleton
from softwarecenter.drawing import color_floats
from widgets.reviews import StarRating

from softwarecenter.enums import SORT_BY_SEARCH_RANKING
from catview import (Category, CategoriesView, get_category_by_name,
                     categories_sorted_by_name)


from softwarecenter.drawing import color_floats, rounded_rect, rounded_rect2

# global cairo surface caches
SURFACE_CACHE = {}
MASK_SURFACE_CACHE = {}

# MAX_POSTER_COUNT should be a number less than the number of featured apps
CAROUSEL_MAX_POSTER_COUNT =      8
CAROUSEL_MIN_POSTER_COUNT =      2
CAROUSEL_ICON_SIZE =             4*mkit.EM

#CAROUSEL_POSTER_CORNER_RADIUS =  int(0.8*mkit.EM)    
CAROUSEL_POSTER_MIN_WIDTH =      15*mkit.EM
CAROUSEL_POSTER_MIN_HEIGHT =     min(64, 4*mkit.EM) + 5*mkit.EM
CAROUSEL_PAGING_DOT_SIZE =       max(8, int(0.6*mkit.EM+0.5))

# as per spec transition timeout should be 15000 (15 seconds)
CAROUSEL_TRANSITION_TIMEOUT =    15000

# spec says the fade duration should be 1 second, these values suffice:
CAROUSEL_FADE_INTERVAL =         25 # msec
CAROUSEL_FADE_STEP =             0.075 # value between 0.0 and 1.0

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
                              
        "application-selected" : (gobject.SIGNAL_RUN_LAST,
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
                 apps_limit=0):

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
        self.section = None

        self._surf_id = 0
        self.section_color = mkit.floats_from_string('#0769BC')

        gtk.Viewport.__init__(self)
        CategoriesView.__init__(self)
        self.set_shadow_type(gtk.SHADOW_NONE)

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        # setup widgets
        a = gtk.Alignment(0.5, 0.0, yscale=1.0)
        self.add(a)

        self.hbox = hb = gtk.HBox()
        a.add(hb)

        self.vbox = vb = gtk.VBox(spacing=18)
        vb.set_border_width(20)
        vb.set_redraw_on_allocate(False)
        hb.pack_start(vb, False)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # appstore stuff
        self.categories = []
        self.header = ''
        self.apps_filter = apps_filter
        self.apps_limit = apps_limit

        # create the cairo caches
#        self._create_surface_cache(datadir)
        self._create_mask_surface_cache(datadir)

        # more stuff
        self._prev_width = 0
        self._poster_sigs = []

        self.vbox.connect('expose-event', self._on_expose)
        self.connect('size-allocate', self._on_allocate, vb)
        self.connect('style-set', self._on_style_set)
        return

    def build(self, desktopdir):
        pass

#    def _create_surface_cache(self, datadir):
#        global SURFACE_CACHE
#        SURFACE_CACHE['n'] = cairo.ImageSurface.create_from_png(os.path.join(datadir, 'images/rshadow-n.png'))
#        SURFACE_CACHE['w'] = cairo.ImageSurface.create_from_png(os.path.join(datadir, 'images/rshadow-w.png'))
#        SURFACE_CACHE['e'] = cairo.ImageSurface.create_from_png(os.path.join(datadir, 'images/rshadow-e.png'))

    def _create_mask_surface_cache(self, datadir):
        global MASK_SURFACE_CACHE
        MASK_SURFACE_CACHE['bloom'] = cairo.ImageSurface.create_from_png(os.path.join(datadir, 'images/bloom.png'))

    def _get_best_fit_width(self):
        if not self.parent: return 1
        # parent alllocation less the sum of all border widths
        return self.parent.allocation.width - 4*mkit.BORDER_WIDTH_LARGE

    def _on_style_set(self, widget, old_style):
        mkit.update_em_metrics()

        global MASK_SURFACE_CACHE
        # cache masked versions of the cached surfaces
        for id, surf in MASK_SURFACE_CACHE.iteritems():
            new_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                          surf.get_width(),
                                          surf.get_height())
            cr = cairo.Context(new_surf)
            cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.light[0]))
            cr.mask_surface(surf,0,0)
            MASK_SURFACE_CACHE[id] = new_surf
            del cr

        self.queue_draw()
        return

    def _on_app_clicked(self, btn):
        app = btn.app
        appname = app[AppStore.COL_APP_NAME]
        pkgname = app[AppStore.COL_PKGNAME]
        rating = app[AppStore.COL_RATING]
        print app
        self.emit("application-selected", Application(appname, pkgname, "", rating))
        self.emit("application-activated", Application(appname, pkgname, "", rating))
        return False

    def _on_category_clicked(self, cat_btn, cat):
        """emit the category-selected signal when a category was clicked"""
        self._logger.debug("on_category_changed: %s" % cat.name)
        self.emit("category-selected", cat)
        return

    def _image_path(self,name):
        return os.path.abspath("%s/images/%s.png" % (self.datadir, name))

    def set_section(self, section):
        self.section = section


class LobbyViewGtk(CategoriesViewGtk):

    def __init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit=0):
        CategoriesViewGtk.__init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit=0)

        self.enquire = xapian.Enquire(self.db.xapiandb)

        # sections
        self.featured_carousel = None
        self.whatsnew_carousel = None
        self.departments = None

        self._prev_width = -1

        self.build(desktopdir)
        return

    def _on_allocate(self, viewport, allocation, vbox):
        self.queue_draw()

        w = min(allocation.width-2, 900)

        if w <= 400 or w == self._prev_width: return True
        self._prev_width = w

        self.featured_carousel.set_width(w)
        self.whatsnew_carousel.set_width(w)

        vbox.set_size_request(w, -1)
        return True

    def _on_expose(self, widget, event):
        a = widget.allocation

        cr = widget.window.cairo_create()
        cr.rectangle(a.x-5, a.y, a.width+10, a.height)
        cr.clip()

        color = color_floats(widget.style.light[0])

        cr.rectangle(widget.allocation)
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: self.section.render(cr, a)

#        # only draw shadows when viewport is sufficiently wide...
#        if a.width >= 900:
#            # shadow on the right side
#            lin = cairo.LinearGradient(a.x+a.width, a.y, a.x+a.width+5, a.y)
#            lin.add_color_stop_rgba(0, 0,0,0, 0.175)
#            lin.add_color_stop_rgba(1, 0,0,0, 0.000)

#            cr.rectangle(a.x+a.width, a.y, 5, a.height)
#            cr.set_source(lin)
#            cr.fill()

#            cr.set_line_width(1)

#            # right side
#            # outer vertical strong line
#            cr.move_to(a.x+a.width+0.5, a.y)
#            cr.rel_line_to(0, a.height)
#            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
#            cr.stroke()

#            # inner vertical highlight
#            cr.move_to(a.x+a.width-0.5, a.y)
#            cr.rel_line_to(0, a.height)
#            cr.set_source_rgba(1,1,1,0.3)
#            cr.stroke()

#            # shadow on the left side
#            lin = cairo.LinearGradient(a.x-5, a.y, a.x, a.y)
#            lin.add_color_stop_rgba(1, 0,0,0, 0.175)
#            lin.add_color_stop_rgba(0, 0,0,0, 0.000)

#            cr.rectangle(a.x-5, a.y, 5, a.height)
#            cr.set_source(lin)
#            cr.fill()

#            # left side
#            # outer vertical strong line
#            cr.move_to(a.x-0.5, a.y)
#            cr.rel_line_to(0, a.height)
#            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
#            cr.stroke()

#            # inner vertical highlight
#            cr.move_to(a.x+0.5, a.y)
#            cr.rel_line_to(0, a.height)
#            cr.set_source_rgba(1,1,1,0.3)
#            cr.stroke()

        # featured carousel
        # draw the info vbox bg
        a = self.featured_carousel.allocation
        rounded_rect(cr, a.x, a.y, a.width, a.height, 5)
        cr.set_source_rgba(*color_floats("#F7F7F7")+(0.75,))
        cr.fill()

        # draw the info header bg
        a = self.featured_carousel.header.allocation
        rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))
        cr.set_source_rgb(*color_floats("#DAD7D3"))
        cr.fill()

        a = self.featured_carousel.allocation
        cr.save()
        rounded_rect(cr, a.x+0.5, a.y+0.5, a.width-1, a.height-1, 5)
        cr.set_source_rgba(*color_floats("#DAD7D3")+(0.3,))
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

        # whatsnew carousel
        # draw the info vbox bg
        a = self.whatsnew_carousel.allocation
        rounded_rect(cr, a.x, a.y, a.width, a.height, 5)
        cr.set_source_rgba(*color_floats("#F7F7F7")+(0.75,))
        cr.fill()

        # draw the info header bg
        a = self.whatsnew_carousel.header.allocation
        rounded_rect2(cr, a.x, a.y, a.width, a.height, (5, 5, 0, 0))
        cr.set_source_rgb(*color_floats("#DAD7D3"))
        cr.fill()

        a = self.whatsnew_carousel.allocation
        cr.save()
        rounded_rect(cr, a.x+0.5, a.y+0.5, a.width-1, a.height-1, 5)
        cr.set_source_rgba(*color_floats("#DAD7D3")+(0.3,))
        cr.set_line_width(1)
        cr.stroke()
        cr.restore()

        self.featured_carousel.draw(cr, self.featured_carousel.allocation, event.area)
        self.whatsnew_carousel.draw(cr, self.whatsnew_carousel.allocation, event.area)

        del cr
        return

    def _on_show_all_clicked(self, show_all_btn):
        self.emit("show-category-applist")

    def _cleanup_poster_sigs(self, *args):
        # clean-up and connect signal handlers
        for sig_id in self._poster_sigs:
            gobject.source_remove(sig_id)
        self._poster_sigs = []
        for poster in self.featured_carousel.posters:
            self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))
        for poster in self.whatsnew_carousel.posters:
            self._poster_sigs.append(poster.connect('clicked', self._on_app_clicked))

#        print self._poster_sigs
        return

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_departments()
        self._append_featured()
        self._append_whatsnew()
        #self._append_recommendations()
        return

    @wait_for_apt_cache_ready
    def _append_recommendations(self):
        """ get recommendations from zeitgeist and add to the view """

        def _show_recommended_apps_widget(query, r_apps): 
            # build UI
            self.hbox = gtk.HBox()
            # Translators: full sentence will be: Welcome back! There is/are %(len)i new recommendation/s for you.
            welcome = gettext.ngettext("Welcome back! There is ",
                                      "Welcome back! There are ",
                                      len(r_apps))
            self.hbox.pack_start(gtk.Label(welcome), False, False)
            # Translators: full sentence will be: Welcome back! There is/are %(len)i new recommendation/s for you.
            label = gettext.ngettext("%(len)i new recommendation",
                                     "%(len)i new recommendations",
                                     len(r_apps)) % { 'len' : len(r_apps) }
            # FIXME: use a gtk.Label() with <a href> instead and put it
            #        all into one label to make it more i18n friendly
            linkbutton = mkit.HLinkButton(label)
            linkbutton.set_underline(True)
            #linkbutton.set_subdued(True)
            self.hbox.pack_start(linkbutton, False, False)
            # Translators: full sentence will be: Welcome back! There is/are %(len)i new recommendation/s for you.
            self.hbox.pack_start(gtk.Label(_(" for you.")), False, False)
            self.vbox.pack_start(self.hbox, False, False)
            self.vbox.reorder_child(self.hbox, 0)
            # build category
            rec_cat = Category("Recommendations", _("Recommendations"), "category-recommendations", query, sortmode=SORT_BY_SEARCH_RANKING)
            linkbutton.connect('clicked', self._on_category_clicked, rec_cat)

            self.show_all() 
              
        def _popular_mimetypes_callback(mimetypes):
            def _find_applications(mimetypes):
                apps = {}
                for count, mimetype in mimetypes:
                    result = self.db.get_most_popular_applications_for_mimetype(mimetype)
                    for app in result:
                        if not app in apps:
                            apps[app] = 0
                        apps[app] += 1
                # this is "sort-by-amount-of-matching-mimetypes", so that
                # e.g. gimp with image/gif, image/png gets sorted higher
                app_tuples = [(v,k) for k, v in apps.iteritems()]
                app_tuples.sort(reverse=True)
                results = []
                for count, app in app_tuples:
                    results.append("AP"+app.pkgname)
                return results

            def _make_query(r_apps):
                if len(r_apps) > 0:
                    return xapian.Query(xapian.Query.OP_OR, r_apps)
                return None
            # get the recommended apps     
            r_apps =_find_applications(mimetypes) 
            if r_apps:
                # build the widget
                _show_recommended_apps_widget(_make_query(r_apps), r_apps)
        
        zeitgeist_singleton.get_popular_mimetypes(_popular_mimetypes_callback)
        

    def _append_featured(self):

        # add some filler...
        padding = gtk.VBox()
        padding.set_size_request(-1, 6)
        self.vbox.pack_start(padding, False)

        featured_cat = get_category_by_name(self.categories,
                                            'Featured')    # untranslated name

        # the spec says the carousel icons should be 4em
        # however, by not using a stock icon size, icons sometimes dont
        # look to great.
        if featured_cat:
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
                                     nonapps_visible=AppStore.NONAPPS_ALWAYS_VISIBLE,
                                     nonblocking_load=False)

            self.featured_carousel = CarouselView(featured_apps, _('Featured'), self.icons)
            self.featured_carousel.more_btn.connect('clicked',
                                                    self._on_category_clicked,
                                                    featured_cat)
            # pack featured carousel into hbox
            self.vbox.pack_start(self.featured_carousel, False)
        return

    def _append_whatsnew(self):
        # create new-apps widget
        new_cat = get_category_by_name(self.categories, 
                                       u"What\u2019s New")
        if new_cat:
            new_apps = AppStore(self.cache,
                                self.db,
                                self.icons,
                                new_cat.query,
                                new_cat.item_limit,
                                new_cat.sortmode,
                                self.apps_filter,
                                icon_size=64,
                                global_icon_cache=False,
                                nonapps_visible=AppStore.NONAPPS_MAYBE_VISIBLE,
                                nonblocking_load=False)

            self.whatsnew_carousel = CarouselView(
                new_apps, _(u"What\u2019s New"), self.icons,
                start_random=False)
            # "What's New", a section for new software.
            self.whatsnew_carousel.more_btn.connect('clicked',
                                                    self._on_category_clicked,
                                                    new_cat)
            # pack new carousel into hbox
            self.vbox.pack_start(self.whatsnew_carousel, False)
        return

    def _append_departments(self):
#        # create departments widget
        self.departments = mkit.LayoutView2(xspacing=20, yspacing=20)

#        # set the departments section to use the label markup we have just defined
        label = mkit.EtchedLabel("<b>%s</b>" % H2 % self.header)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        self.vbox.pack_start(label, False)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)
        layout = self.create_pango_layout('')

        max_w = 200
#        e = self.enquire

        for cat in sorted_cats:
            if 'carousel-only' not in cat.flags:
                layout.set_text(cat.name)
                w = layout.get_pixel_extents()[1][2] + 40

#                e.set_query(cat.query)
#                # limiting the size here does not make it faster
#                matches = e.get_mset(0, len(self.db))
#                estimate = matches.get_matches_estimated()

                max_w = max(w, max_w)

                cat_btn = CategoryButton(cat.name, cat.iconname)
                cat_btn.connect('clicked', self._on_category_clicked, cat)
                # append the department to the departments widget
                self.departments.add(cat_btn)

        self.departments.min_col_width = max_w

        # append the departments section to the page
        self.vbox.pack_start(self.departments, False)
        return

    def start_carousels(self):
        if self.featured_carousel:
            self.featured_carousel.start()
        if self.whatsnew_carousel:
            self.whatsnew_carousel.start(offset=5000)
        return

    def stop_carousels(self):
        if self.featured_carousel:
            self.featured_carousel.stop()
        if self.whatsnew_carousel:
            self.whatsnew_carousel.stop()
        return

    def build(self, desktopdir):
        self.categories = self.parse_applications_menu(desktopdir)
        self.header = _('Departments')
        print 'Build'
        self._build_homepage_view()
        return


class SubCategoryViewGtk(CategoriesViewGtk):

    def __init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit=0,
                 root_category=None):
        CategoriesViewGtk.__init__(self, 
                 datadir,
                 desktopdir, 
                 cache,
                 db,
                 icons,
                 apps_filter,
                 apps_limit)

        # data
        self.root_category = root_category

        # sections
        self.departments = None
        return

    def _on_allocate(self, viewport, allocation, vbox):
        self.queue_draw()

        w = min(allocation.width-2, 900)

        if w <= 400 or w == self._prev_width: return True
        self._prev_width = w

#        self.featured_carousel.set_width(w)
#        self.whatsnew_carousel.set_width(w)

        vbox.set_size_request(w, -1)
        return True

    def _on_expose(self, widget, event):
        a = widget.allocation

        cr = widget.window.cairo_create()
        cr.rectangle(a.x-5, a.y, a.width+10, a.height)
        cr.clip()

        color = color_floats(widget.style.light[0])

        cr.rectangle(widget.allocation)
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: self.section.render(cr, a)

        # only draw shadows when viewport is sufficiently wide...
        if a.width >= 900:
            # shadow on the right side
            lin = cairo.LinearGradient(a.x+a.width, a.y, a.x+a.width+5, a.y)
            lin.add_color_stop_rgba(0, 0,0,0, 0.175)
            lin.add_color_stop_rgba(1, 0,0,0, 0.000)

            cr.rectangle(a.x+a.width, a.y, 5, a.height)
            cr.set_source(lin)
            cr.fill()

            cr.set_line_width(1)

            # right side
            # outer vertical strong line
            cr.move_to(a.x+a.width+0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
            cr.stroke()

            # inner vertical highlight
            cr.move_to(a.x+a.width-0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgba(1,1,1,0.3)
            cr.stroke()

            # shadow on the left side
            lin = cairo.LinearGradient(a.x-5, a.y, a.x, a.y)
            lin.add_color_stop_rgba(1, 0,0,0, 0.175)
            lin.add_color_stop_rgba(0, 0,0,0, 0.000)

            cr.rectangle(a.x-5, a.y, 5, a.height)
            cr.set_source(lin)
            cr.fill()

            # left side
            # outer vertical strong line
            cr.move_to(a.x-0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgb(*color_floats(widget.style.dark[self.state]))
            cr.stroke()

            # inner vertical highlight
            cr.move_to(a.x+0.5, a.y)
            cr.rel_line_to(0, a.height)
            cr.set_source_rgba(1,1,1,0.3)
            cr.stroke()
        del cr


    def _append_subcat_departments(self, root_category, num_items):
        # create departments widget
        if not self.departments:
            self.departments = mkit.LayoutView2()
            # append the departments section to the page
            self.vbox.pack_start(self.departments)
        else:
            self.departments.clear()

        # set the departments section to use the label
        header = gobject.markup_escape_text(self.header)
#        self.departments.set_label(H2 % header)

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
            self.departments.add(cat_btn)

        # append an additional button to show all of the items in the category
        name = gobject.markup_escape_text(_("All %s") % num_items)
        show_all_btn = SubcategoryButton(name, "category-show-all", self.icons)
        all_cat = Category("All", _("All"), "category-show-all", root_category.query)
        show_all_btn.connect('clicked', self._on_category_clicked, all_cat)
        self.departments.add(show_all_btn)

        self.departments.layout(self.departments.allocation.width,
                                self.departments.yspacing)
        return

    def _build_subcat_view(self, root_category, num_items):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments(root_category, num_items)
        return

    def set_subcategory(self, root_category, num_items=0, block=False):
        # nothing to do
        if self.categories == root_category.subcategories:
            return
        self.header = root_category.name

#        ico_inf = self.icons.lookup_icon(root_category.iconname, 150, 0)
        self.categories = root_category.subcategories
        self._build_subcat_view(root_category, num_items)
        return

    #def build(self, desktopdir):
        #self.in_subsection = True
        #self.set_subcategory(self.root_category)
        #return


class CarouselView(gtk.VBox):

    def __init__(self, carousel_apps, title, icons, start_random=True):
        gtk.VBox.__init__(self, spacing=6)

        self.cache = carousel_apps.cache

        self.header = gtk.HBox(spacing=12)
        self.pack_start(self.header)

        self.title = mkit.EtchedLabel(title)
        self.title.set_alignment(0,0.5)
        self.title.set_padding(6,6)
        self.header.pack_start(self.title, False)

        self.icons = icons

        self.hbox = gtk.HBox()
        self.hbox.set_spacing(6)
        self.hbox.set_border_width(6)
        self.hbox.set_homogeneous(True)
        self.pack_start(self.hbox, False)

        self.page_sel = PageSelector()
        self.page_sel.set_border_width(12)
        self.pack_end(self.page_sel, False)

        self.title = title
        self.posters = []
        self.n_posters = 0
        self.set_redraw_on_allocate(False)
        self.carousel_apps = carousel_apps  # an AppStore

        label = _('All')
        self.more_btn = LinkButton()
        self.more_btn.set_label(label)
#        self.more_btn.set_subdued()

        self.more_btn.a11y = self.more_btn.get_accessible()
        self.more_btn.a11y.set_name(_("%s section: show all") % title )

        a = gtk.Alignment(1, 0.5)
        a.set_padding(6, 6, 6, 6)
        a.add(self.more_btn)

        self.header.pack_end(a, False)

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

        self._transition_ids = []
        self._is_playing = False
        self._play_offset = 0
        self._user_offset_override = None
        self._width = 0
        self._alpha = 1.0
        self._fader = 0
        self._layout = None
        self._height = -1

        self.show_all()

        self.page_sel.connect('page-selected', self._on_page_clicked)
        return

    def _on_page_clicked(self, page_sel, page):
        self._offset = page*self.n_posters
        self.stop(); self.start()
        self.transition()
        return

    @wait_for_apt_cache_ready
    def _build_view(self, width):
        if not self.carousel_apps or len(self.carousel_apps) == 0:
            return

        old_n_cols = len(self.hbox.get_children())
        n_cols = max(2, width / (CAROUSEL_POSTER_MIN_WIDTH + self.hbox.get_spacing()))

        if old_n_cols == n_cols: return True

        # if n_cols is smaller than our previous number of posters,
        # then we remove just the right number of posters from the carousel
        if n_cols < self.n_posters:
            n_remove = self.n_posters - n_cols
#            self._offset -= n_remove
            for i in range(n_remove):
                poster = self.posters[i]
                # leave no traces remaining (of the poster)
                poster.destroy()
                del self.posters[i]

        # if n is greater than our previous number of posters,
        # we need to pack in extra posters
        else:
            n_add = n_cols - self.n_posters
            for i in range(n_add):
                poster = CarouselPoster2(self.carousel_apps.db,
                                         self.carousel_apps.cache,
                                         icon_size=self._icon_size,
                                         icons=self.icons)

                self.posters.append(poster)
                self.hbox.pack_start(poster)
                poster.show()

        # set how many PagingDot's the PageSelector should display
        pages = float(len(self.carousel_apps)) / n_cols
        #print "pages: ", pages
        if pages - int(pages) > 0.0:
            pages += 1

        #print len(self.carousel_apps), n, pages
        self.page_sel.set_n_pages(int(pages))
        self.n_posters = n_cols

        self._update_pagesel()
        self.get_ancestor(LobbyViewGtk)._cleanup_poster_sigs()
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
        #temporary fix for crash in bug 694836
        if self.n_posters> 0:
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

    def stop(self):
        #print 'Stopping ...'
        if not self._is_playing: 
            return
        self._alpha = 1.0
        self._is_playing = False
        for id in self._transition_ids:
            gobject.source_remove(id)
        return

    def start(self, offset=0):
        if self._is_playing: 
            return
        #print 'Starting ...', offset
        self._is_playing = True
        if not offset:
            self._transition_ids.append(gobject.timeout_add(CAROUSEL_TRANSITION_TIMEOUT,
                                             self.transition))
            return

        def _offset_start_cb():
            self._transition_ids.append(gobject.timeout_add(CAROUSEL_TRANSITION_TIMEOUT,
                                         self.transition))
            #print 'offset'
            return False

        self._play_offset = 0
        self._transition_ids.append(gobject.timeout_add(offset, _offset_start_cb))
        return

    def next(self):
        self._set_next(fade_in=False)
        return

    def previous(self):
        self._offset -= self.n_posters
        self._set_next(fade_in=False)
        return

    def transition(self, loop=True):
        for poster in self.posters:
            if poster.state > 0:
                return loop
        self._fader = gobject.timeout_add(CAROUSEL_FADE_INTERVAL,
                                          self._fade_out)
        return loop

    def set_width(self, width):
        self._width = width
        self.page_sel.set_width(width)
        self._build_view(width)
        return

    def get_posters(self):
        return self.posters

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

    def draw(self, cr, a, expose_area):
        if mkit.not_overlapping(a, expose_area): return

        self.more_btn.draw(cr, self.more_btn.allocation, expose_area)

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


class BubbleLabel(gtk.Label):

    def __init__(self, *args, **kwargs):
        gtk.Label.__init__(self, *args, **kwargs)

        self.connect('expose-event', self._on_expose)
        return

    def _on_expose(self, w, e):
        a = w.allocation
        l = w.get_layout()
        lw, lh = l.get_pixel_extents()[1][2:]
        ax, ay = w.get_alignment()
        px, py = w.get_padding()

        x = int(a.x + (a.width - lw - 2*px) * ax)
        y = int(a.y + (a.height - lh - 2*py) * ay)

        cr = w.window.cairo_create()

        # draw action bubble background
        rounded_rect(cr, x, y, lw+2*px, lh+2*py, 5)
        color = w.style.dark[w.state].to_string()
        cr.set_source_rgb(*color_floats(color))
        cr.fill()

        # bubble number
        color = w.style.white.to_string()
        l.set_markup('<span color="%s">%s</span>' % (color, w.get_label()))

        del cr
        return


class Button(gtk.EventBox):

    __gsignals__ = {
        "clicked" : (gobject.SIGNAL_RUN_LAST,
                     gobject.TYPE_NONE, 
                     (),)
        }

    def __init__(self):
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.set_flags(gtk.CAN_FOCUS)
        self.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                        gtk.gdk.BUTTON_RELEASE_MASK|
                        gtk.gdk.KEY_RELEASE_MASK|
                        gtk.gdk.KEY_PRESS_MASK|
                        gtk.gdk.ENTER_NOTIFY_MASK|
                        gtk.gdk.LEAVE_NOTIFY_MASK)

        self._button_press_origin = None
        self._cursor = gtk.gdk.Cursor(cursor_type=gtk.gdk.HAND2)

        self.connect("button-press-event", self._on_button_press)
        self.connect("button-release-event", self._on_button_release)
        self.connect('enter-notify-event', self._on_enter)
        self.connect('leave-notify-event', self._on_leave)
        return

    def _on_button_press(self, btn, event):
        if event.button != 1: return
        self._button_press_origin = btn
        self.set_state(gtk.STATE_ACTIVE)

        if hasattr(self, 'label_list'):
            for v in self.label_list:
                l = getattr(self, v)
                self._label_colorise_active(l)
        return

    def _on_button_release(self, btn, event):

        def clicked(w):
            w.emit('clicked')

        if event.button != 1:
            self.queue_draw()
            return

        region = gtk.gdk.region_rectangle(self.allocation)
        if not region.point_in(*self.window.get_pointer()[:2]):
            self._button_press_origin = None
            self.set_state(gtk.STATE_NORMAL)
            return

        self._button_press_origin = None
        self.set_state(gtk.STATE_PRELIGHT)

        if hasattr(self, 'label_list'):
            for v in self.label_list:
                l = getattr(self, v)
                self._label_colorise_normal(l)

        gobject.timeout_add(50, clicked, btn)
        return

    def _on_enter(self, btn, event):
        if self == self._button_press_origin:
            self.set_state(gtk.STATE_ACTIVE)
        else:
            self.set_state(gtk.STATE_PRELIGHT)

        self.window.set_cursor(self._cursor)
        return

    def _on_leave(self, btn, event):
        self.set_state(gtk.STATE_NORMAL)
        self.window.set_cursor(None)
        return

    def _label_colorise_active(self, label):
        c = self.style.base[gtk.STATE_SELECTED]
        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = label.get_layout()
        attrs = layout.get_attributes()

        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return

    def _label_colorise_normal(self, label):
        if self.state == gtk.STATE_PRELIGHT or \
            self.has_focus():
            c = self.style.text[self.state]
        else:
            c = self.style.dark[self.state]

        attr = pango.AttrForeground(c.red,
                                    c.green,
                                    c.blue,
                                    0, -1)

        layout = label.get_layout()
        attrs = layout.get_attributes()

        if not attrs:
            attrs = pango.AttrList()

        attrs.change(attr)
        layout.set_attributes(attrs)
        return


class LinkButton(Button):

    def __init__(self):
        Button.__init__(self)
        self.label = mkit.EtchedLabel()
        self.add(self.label)
        self.show_all()

        self.label_list = ('label',)
        return

    def set_label(self, label):
        self.label.set_markup('<u>%s</u>' % label)
        return

#    def set_subdued(self, is_subdued):
#        self.subdued = is_subdued
#        return

    def draw(self, *args):
        return


class CategoryButton(Button):

    SPACING = 6
    ICON_SIZE = gtk.ICON_SIZE_LARGE_TOOLBAR

    def __init__(self, label, iconname):
        Button.__init__(self)

        hb = gtk.HBox(spacing=self.SPACING)
        self.add(hb)

        hb.pack_start(gtk.image_new_from_icon_name(iconname, self.ICON_SIZE), False)
        self.label = label = mkit.EtchedLabel(label)
        label.set_alignment(0, 0.5)
        label.set_padding(0, 6)
        hb.pack_start(label, False)

#        if estimate / 1000 >= 1:
#            e = estimate / 1000
#            elabel = BubbleLabel('<small>%s%s</small>' % (e, _('K')))
#        else:
#            elabel = BubbleLabel('<small>%s</small>' % estimate)

#        elabel.set_padding(4, 0)
#        elabel.set_use_markup(True)
#        hb.pack_start(elabel, False)

        self.label_list = ('label',)
        return


class SubcategoryButton(mkit.VLinkButton):

    ICON_SIZE = 48
    MAX_WIDTH  = 12*mkit.EM
    MAX_HEIGHT = 9*mkit.EM

    def __init__(self, markup, icon_name, icons):
        mkit.VLinkButton.__init__(self, markup, icon_name, self.ICON_SIZE, icons)
        self.set_border_width(mkit.BORDER_WIDTH_SMALL)
        self.set_max_width(self.MAX_WIDTH)
        #self.set_max_width(self.MAX_HEIGHT)
        self.box.set_size_request(self.MAX_WIDTH, self.MAX_HEIGHT)
        return


class CarouselPoster2(Button):

    def __init__(self, db, cache, icon_size=48, icons=None):
        Button.__init__(self)

        self.hbox = gtk.HBox(spacing=8)
        self.add(self.hbox)

        self.db = db
        self.cache = cache
        self.icon_size = icon_size
        self.icons = icons

        self.app = None
        self.alpha = 1.0
        self._cacher = 0
        
        self._height = 0

        self._surf_cache = None

        self._build_ui(icon_size)

        self.connect('expose-event', self._on_expose)
        return

    def _build_ui(self, icon_size):
        self.image = gtk.Image()
        self.image.set_size_request(icon_size, icon_size)

        self.label = gtk.Label()
        self.label.set_alignment(0, 0.5)
        self.label.set_line_wrap(True)

        self.nrreviews = gtk.Label()
        self.nrreviews.set_alignment(0, 0.5)

        self.rating = StarRating()
        self.rating.set(0, 0.5, 0, 0)

        self.hbox.pack_start(self.image, False)

        inner_vbox = gtk.VBox(spacing=3)

        a = gtk.Alignment(0, 0)
        a.set_padding(12, 0, 0, 0)
        a.add(inner_vbox)

        self.hbox.pack_start(a, False)

        inner_vbox.pack_start(self.label, False)
        inner_vbox.pack_start(self.rating, False)
        inner_vbox.pack_start(self.nrreviews, False)

        self.label_list = ('label', 'nrreviews')


        self.show_all()

        self.connect('size-allocate', self._on_allocate, self.label)
        return

    def _on_allocate(self, w, allocation, label):
        w = allocation.width - self.icon_size - self.hbox.get_spacing() - 2*self.hbox.get_border_width()
        label.set_size_request(max(1, w), -1)

        if allocation.height > self._height:
            self.set_size_request(-1, allocation.height)
            self._height = allocation.height

        # cache an ImageSurface for transitions
        self._cache_surf()
        return

    def _on_expose(self, w, e):
        if self.alpha >= 1.0 or not self._surf_cache: return

        a = w.allocation
        cr = w.window.cairo_create()

        cr.set_source_surface(self._surf_cache, a.x, a.y)

        cr.paint_with_alpha(self.alpha)
        return True

    def _cache_surf(self, force=False):

        def _cache_surf():
            if not self.app: return

            a = self.allocation

#            print 'CacheSurf', self.app[0]

            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                      a.width,
                                      a.height)

            cr = cairo.Context(surf)
            cr = gtk.gdk.CairoContext(pangocairo.CairoContext(cr))

            _a = self.image.allocation
            pb = self.image.get_pixbuf()

            if pb:
                w, h = pb.get_width(), pb.get_height()

                cr.set_source_pixbuf(self.image.get_pixbuf(),
                                     a.x - _a.x + (_a.width - w)/2,
                                     a.y - _a.y + (_a.height - h)/2)
                cr.paint()

            cr.set_source_color(self.style.text[self.state])
            cr.move_to(self.label.allocation.x - a.x, self.label.allocation.y - a.y)
            cr.layout_path(self.label.get_layout())
            cr.fill()

            if self.nrreviews.get_property('visible'):
                cr.move_to(self.nrreviews.allocation.x - a.x,
                           self.nrreviews.allocation.y - a.y)
                cr.layout_path(self.nrreviews.get_layout())
                cr.fill()

            if self.rating.get_property('visible'):
                for star in self.rating.get_stars():
                    sa = star.allocation
                    _a = gtk.gdk.Rectangle(sa.x - a.x, sa.y - a.y, sa.width, sa.height)
                    star.draw(cr, _a)

            del cr

            self._surf_cache = surf
            return False

        if self._cacher:
            gobject.source_remove(self._cacher)
            self._cacher = 0

        if not force:
            self._cacher = gobject.idle_add(_cache_surf)
        else:
            _cache_surf()
        return

    def set_application(self, app):
#        print 'NewApplication', app[0]
        self.app = app

        a = Application(appname=app[AppStore.COL_APP_NAME],
                        pkgname=app[AppStore.COL_PKGNAME],
                        popcon=app[AppStore.COL_RATING])

        nr_reviews = app[AppStore.COL_NR_REVIEWS]

        d = a.get_details(self.db)

        name = app[AppStore.COL_APP_NAME]

        markup = '%s' % glib.markup_escape_text(name)
        pb = app[AppStore.COL_ICON]

        tw = 48    # target width
        if pb.get_width() < tw:
            pb = pb.scale_simple(tw, tw, gtk.gdk.INTERP_TILES)

        self.image.set_from_pixbuf(pb)
        self.label.set_markup('<span font_desc="9">%s</span>' % markup)

        if not a.popcon:
            self.nrreviews.hide()
        else:
            self.nrreviews.show()

            s = gettext.ngettext(
                "%(nr_ratings)i Rating",
                "%(nr_ratings)i Ratings",
                nr_reviews) % { 'nr_ratings' : nr_reviews, }

            self.nrreviews.set_markup('<small>%s</small>' % s)

        self.rating.set_rating(a.popcon)

        # set a11y text
        self.get_accessible().set_name(name)

        self._cache_surf(force=True)
        return

    def draw(self, cr, a, event_area, alpha):
        self.alpha = alpha
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
            w += PagingDot.DOT_SIZE + mkit.SPACING_MED

            if w > max_w:
                rowbox = gtk.HBox(spacing=mkit.SPACING_MED)
                row = gtk.Alignment(0.5, 0.5)
                row.add(rowbox)

                self.vbox.pack_start(row, expand=True)
                w = PagingDot.DOT_SIZE + mkit.SPACING_MED

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

    DOT_SIZE =       max(8, int(0.6*mkit.EM+0.5))

    def __init__(self, page_number):
        mkit.LinkButton.__init__(self, None, None, None)
        self.set_size_request(-1, self.DOT_SIZE)
        self.is_selected = False
        self.page_number = page_number

        # a11y for page selector
        self.set_property("can-focus", True)
        self.a11y = self.get_accessible()
        self.a11y.set_name(_("Go to page %d") % (self.page_number + 1))
        return

    def calc_width(self):
        return self.DOT_SIZE

    def draw(self, cr, a, expose_area, alpha):
        cr.save()
        #cr.rectangle(a)
        #cr.clip()
        r,g,b = mkit.floats_from_gdkcolor(self.style.dark[self.state])

        
        cr.save()
        cr.translate(0.5,0.5)
        cr.set_line_width(1)
        c = mkit.ShapeCircle()
        c.layout(cr, a.x, a.y, a.width-1, a.height-1)

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
