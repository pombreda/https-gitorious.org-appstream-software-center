import atk
import os
import gtk
import gobject
import gettext
import logging
import xapian

from gettext import gettext as _

from widgets import mkit
from appview import AppStore

from softwarecenter.db.application import Application

from softwarecenter.enums import SORT_BY_SEARCH_RANKING
from softwarecenter.utils import wait_for_apt_cache_ready
from softwarecenter.backend.zeitgeist_simple import zeitgeist_singleton
from softwarecenter.drawing import color_floats, rounded_rect, rounded_rect2

from widgets.carousel import CarouselView
from widgets.buttons import CategoryButton, SubcategoryButton

from catview import (Category, CategoriesView, get_category_by_name,
                     categories_sorted_by_name)



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

        # more stuff
        self._prev_width = 0
        self._poster_sigs = []

        self._allocation = None

        self.vbox.connect('expose-event', self._on_expose, a)
        self.vbox.connect('size-allocate', self._on_allocate)
#        self.connect('style-set', self._on_style_set)
        return

    def build(self, desktopdir):
        pass

    def _on_allocate(self, widget, allocation):
        logging.getLogger("softwarecenter.view.allocation").debug("on_alloc widget=%s, allocation=%s" % (widget, allocation))

        self.queue_draw()

        if self._allocation == allocation: 
            logging.getLogger("softwarecenter.view.allocation").debug("LobbyviewGtk skipped!")
            return True
        self._allocation = allocation

        w = min(self.allocation.width-2, 70*mkit.EM)

        widget.set_size_request(w, -1)
        return True

    def _on_app_clicked(self, btn):
        app = btn.app
        appname = app[AppStore.COL_APP_NAME]
        pkgname = app[AppStore.COL_PKGNAME]
        rating = app[AppStore.COL_RATING]
        self.emit("application-selected", Application(appname, pkgname, "", rating))
        self.emit("application-activated", Application(appname, pkgname, "", rating))
        return False

    def _on_category_clicked(self, cat_btn, cat):
        """emit the category-selected signal when a category was clicked"""
        self._logger.debug("on_category_changed: %s" % cat.name)
        self.emit("category-selected", cat)
        return

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

#        self.enquire = xapian.Enquire(self.db.xapiandb)

        # sections
        self.featured_carousel = None
        self.whatsnew_carousel = None
        self.departments = None

        self._prev_width = -1

        self.build(desktopdir)
        return

    def _on_expose(self, widget, event, alignment):
        cr = widget.window.cairo_create()
        cr.rectangle(alignment.allocation)
        cr.clip_preserve()

        color = color_floats(widget.style.light[0])
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: self.section.render(cr, alignment.allocation)

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
        self._append_recommendations()
        return

    @wait_for_apt_cache_ready
    def _append_recommendations(self):
        """ get recommendations from zeitgeist and add to the view """

        def _show_recommended_apps_widget(query, r_apps):
            recommended = gtk.Label()
            recommended_text = gettext.ngettext(
             "Welcome back! There is <a href=\"\">%i new recommendation</a>"
                                                   " for you." % len(r_apps),
             "Welcome back! There are <a href=\"\">%i new recommendations</a>"
                                                     " for you." % len(r_apps),
             len(r_apps))
            recommended.set_markup(recommended_text)
            recommended.set_visible(True)
            recommended.get_accessible().set_role(atk.ROLE_PUSH_BUTTON)
            recommended.set_alignment(0,-1)
            self.vbox.pack_start(recommended, False, False)
            self.vbox.reorder_child(recommended, 0)

            # build category
            rec_cat = Category("Recommendations",
                               _("Recommendations"),
                               "category-recommendations",
                               query,
                               sortmode=SORT_BY_SEARCH_RANKING)
            recommended.connect('activate-link',
                                self._on_recommended_clicked,
                                rec_cat)
              
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

    def _on_recommended_clicked(self, link, uri, rec_cat):
        self._on_category_clicked(self, rec_cat)
        return True # mutter..

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

            self.featured_carousel = CarouselView(self,
                                                  featured_apps,
                                                  _('Featured'),
                                                  self.icons)

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

            self.whatsnew_carousel = CarouselView(self,
                                                  new_apps,
                                                  _(u"What\u2019s New"),
                                                  self.icons,
                                                  start_random=False)

            self.whatsnew_carousel.more_btn.connect('clicked',
                                                    self._on_category_clicked,
                                                    new_cat)
            # pack whatsnew carousel into hbox
            self.vbox.pack_start(self.whatsnew_carousel, False)
        return

    def _append_departments(self):
#        # create departments widget
        self.departments = mkit.LayoutView2(xspacing=20, yspacing=12)

#        # set the departments section to use the label markup we have just defined
        label = mkit.EtchedLabel("<b><big>%s</big></b>" % self.header)
        label.set_use_markup(True)
        label.set_alignment(0, 0.5)
        self.vbox.pack_start(label, False)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)
        layout = self.create_pango_layout('')

        max_w = 200

        for cat in sorted_cats:
            if 'carousel-only' not in cat.flags:
                layout.set_text(cat.name)
                w = layout.get_pixel_extents()[1][2] + 32
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

    def _on_expose(self, widget, event, alignment):
        cr = widget.window.cairo_create()
        cr.rectangle(alignment.allocation)
        cr.clip_preserve()

        color = color_floats(widget.style.light[0])

        cr.rectangle(alignment.allocation)
        cr.set_source_rgba(*color+(0.6,))
        cr.fill()

        # paint the section backdrop
        if self.section: self.section.render(cr, alignment.allocation)

        del cr

    def _append_subcat_departments(self, root_category, num_items):
        m = "<b><big>%s</big></b>"
        if self.departments is None:
            self.subcat_label = mkit.EtchedLabel()
            self.subcat_label.set_use_markup(True)
            self.subcat_label.set_alignment(0, 0.5)
            self.vbox.pack_start(self.subcat_label, False)

            self.departments = mkit.LayoutView2(xspacing=20, yspacing=12)
            self.departments.min_col_width = 10*mkit.EM

            # append the departments section to the page
            self.vbox.pack_start(self.departments)

        # set the subcat header
        self.subcat_label.set_markup(m % gobject.markup_escape_text(self.header))

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        buttons = []
        for cat in sorted_cats:
            cat_btn = SubcategoryButton(cat.name, cat.iconname)
            cat_btn.connect('clicked', self._on_category_clicked, cat)
            buttons.append(cat_btn)

        # append an additional button to show all of the items in the category
        name = gobject.markup_escape_text('%s %s' % (_("All"), num_items))
        show_all_btn = SubcategoryButton(name, "category-show-all")
        all_cat = Category("All", _("All"), "category-show-all", root_category.query)
        show_all_btn.connect('clicked', self._on_category_clicked, all_cat)
        buttons.append(show_all_btn)

        # append the cat buttons to the departments widget
        self.departments.set_widgets(buttons)

        self.show_all()
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
