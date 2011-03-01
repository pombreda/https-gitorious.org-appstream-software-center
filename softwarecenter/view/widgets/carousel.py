import atk
import gtk
import gobject
import cairo
import pangocairo
import random

from reviews import StarRating

from mkit import EM, EtchedLabel, ShapeCircle, LinkButton, \
                 LinkButtonLight, Button, not_overlapping

from softwarecenter.db.database import Application
from softwarecenter.models.appstore import AppStore

from softwarecenter.drawing import color_floats
from softwarecenter.utils import wait_for_apt_cache_ready

from gettext import gettext as _


class CarouselView(gtk.VBox):

    # as per spec transition timeout should be 15000 (15 seconds)
    TRANSITION_TIMEOUT =    15000

    # spec says the fade duration should be 1 second, these values suffice:
    FADE_INTERVAL =         25 # msec
    FADE_STEP =             0.075 # value between 0.0 and 1.0

    POSTER_MIN_WIDTH =      15*EM


    def __init__(self, view, carousel_apps, title, icons, start_random=True):
        gtk.VBox.__init__(self, spacing=6)

        self.view = view
        self.cache = carousel_apps.cache

        self.header = gtk.HBox(spacing=12)
        self.pack_start(self.header)

        self.title = EtchedLabel(title)
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
        self.more_btn = LinkButtonLight()
        self.more_btn.set_label(label)
#        self.more_btn.set_subdued()

        self.more_btn.a11y = self.more_btn.get_accessible()
        self.more_btn.a11y.set_name(_("show all"))
        self.more_btn.a11y.set_role(atk.ROLE_PUSH_BUTTON)

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
        self.connect('size-allocate', self._on_allocate)
        return

    def _on_allocate(self, widget, allocation):
        if allocation.width == self._width: return
        self._width = allocation.width
        self._build_view(self._width)
        return

    def _on_page_clicked(self, page_sel, page):
        self.stop()
        self._offset = page*self.n_posters
        self._update_poster_content()
        self._alpha = 1.0
        self.queue_draw()
        self.start()
        return

    @wait_for_apt_cache_ready
    def _build_view(self, width):
        if not self.carousel_apps or len(self.carousel_apps) == 0:
            return

        old_n_cols = len(self.hbox.get_children())
        n_cols = max(2, width / (CarouselView.POSTER_MIN_WIDTH + self.hbox.get_spacing()))

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
        self.view._cleanup_poster_sigs()
        return

    def _fade_in(self):
        self._alpha += CarouselView.FADE_STEP
        if self._alpha >= 1.0:
            self._alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _fade_out(self):
        self._alpha -= CarouselView.FADE_STEP
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
            self._fader = gobject.timeout_add(CarouselView.FADE_INTERVAL,
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
            self._transition_ids.append(
                gobject.timeout_add(CarouselView.TRANSITION_TIMEOUT,
                                    self.transition))
            return

        def _offset_start_cb():
            self._transition_ids.append(
                gobject.timeout_add(CarouselView.TRANSITION_TIMEOUT,
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
            if poster.state > 0 or poster.is_focus():
                return loop
        self._fader = gobject.timeout_add(CarouselView.FADE_INTERVAL,
                                          self._fade_out)
        return loop

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
        if not_overlapping(a, expose_area): return

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



class CarouselPoster2(Button):

    def __init__(self, db, cache, icon_size=48, icons=None):
        Button.__init__(self)

        self.hbox = gtk.HBox(spacing=8)
        self.hbox.set_border_width(3)
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

        self.a11y = self.get_accessible()
        self.a11y.set_role(atk.ROLE_PUSH_BUTTON)

        self.connect('expose-event', self._on_expose)
        return

    def _build_ui(self, icon_size):
        self.image = gtk.Image()
        self.image.set_size_request(icon_size, icon_size)

        self.label = gtk.Label()
        self.label.set_alignment(0, 0.5)
        self.label.set_line_wrap(True)

#        self.nrreviews = gtk.Label()
#        self.nrreviews.is_subtle = True
#        self.nrreviews.set_alignment(0, 0.5)

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
#        inner_vbox.pack_start(self.nrreviews, False)

        self.label_list = ('label',)


        self.show_all()

        self.connect('size-allocate', self._on_allocate, self.label)
        return

    def _on_allocate(self, w, allocation, label):
        w = allocation.width - self.icon_size - self.hbox.get_spacing() - 2*self.hbox.get_border_width()
        label.set_size_request(max(1, w), -1)

        self._surf_cache = None
        return

    def _on_expose(self, w, e):
        if not self._surf_cache: self._cache_surf()

        a = w.allocation

        if self.has_focus():
            w.style.paint_focus(w.window,
                                w.state,
                                w.allocation,
                                w,
                                'expander',
                                a.x, a.y,
                                a.width, a.height)

        if self.alpha >= 1.0:

            if (w.state == gtk.STATE_ACTIVE):
                for child in w:
                    w.propagate_expose(child, e)

                c = w.style.base[gtk.STATE_SELECTED]
                cr = w.window.cairo_create()
                cr.set_source_rgba(c.red_float,
                                   c.green_float,
                                   c.blue_float,
                                   0.25)

                cr.mask_surface(self._surf_cache, a.x, a.y)
            else:
                return False
            return True

        cr = w.window.cairo_create()
        cr.set_source_surface(self._surf_cache, a.x, a.y)
        cr.paint_with_alpha(self.alpha)

        return True

    def _cache_surf(self):
        if not self.app: return

        a = self.allocation
        bw = self.hbox.get_border_width()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                  a.width,
                                  a.height)

        cr = cairo.Context(surf)
        cr = gtk.gdk.CairoContext(pangocairo.CairoContext(cr))

        pb = self.image.get_pixbuf()
        if pb:
            w, h = pb.get_width(), pb.get_height()

            cr.set_source_pixbuf(self.image.get_pixbuf(),
                                 bw + (self.image.allocation.width - w)/2,
                                 bw + (self.image.allocation.height - h)/2)
            cr.paint()

        cr.set_source_color(self.style.text[self.state])
        cr.move_to(self.label.allocation.x - a.x,
                   self.label.allocation.y - a.y)
        cr.layout_path(self.label.get_layout())
        cr.fill()

#        if self.nrreviews.get_property('visible'):
#            cr.move_to(self.nrreviews.allocation.x - a.x,
#                       self.nrreviews.allocation.y - a.y)
#            cr.layout_path(self.nrreviews.get_layout())
#            cr.set_source_color(self.style.dark[self.state])
#            cr.fill()

        if self.rating.get_property('visible'):
            for star in self.rating.get_stars():
                sa = star.allocation
                _a = gtk.gdk.Rectangle(sa.x - a.x, sa.y - a.y, sa.width, sa.height)
                star.draw(cr, _a)

        del cr

        self._surf_cache = surf
        return

    def set_application(self, app):
        self.app = app
        self._surf_cache = None

        a = Application(appname=app[AppStore.COL_APP_NAME],
                        pkgname=app[AppStore.COL_PKGNAME],
                        popcon=app[AppStore.COL_RATING])

        nr_reviews = app[AppStore.COL_NR_REVIEWS]

        d = a.get_details(self.db)

        name = app[AppStore.COL_APP_NAME]

        markup = '%s' % gobject.markup_escape_text(name)
        pb = app[AppStore.COL_ICON]

        tw = 48    # target width
        if pb.get_width() < tw:
            pb = pb.scale_simple(tw, tw, gtk.gdk.INTERP_TILES)

        self.image.set_from_pixbuf(pb)
        self.label.set_markup('<span font_desc="9">%s</span>' % markup)

#        if not a.popcon:
#            self.nrreviews.hide()
#        else:
#            self.nrreviews.show()

#            s = gettext.ngettext(
#                "%(nr_ratings)i Rating",
#                "%(nr_ratings)i Ratings",
#                nr_reviews) % { 'nr_ratings' : nr_reviews, }

#            m = '<span color="%s"><small>%s</small></span>'
#            self.nrreviews.set_markup(m % (self.style.dark[gtk.STATE_NORMAL], s))

        self.rating.set_rating(a.popcon)

        # set a11y text
        self.a11y.set_name(name)

        self._cache_surf()
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
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.show_all()

        self.n_pages = 0
        self.selected = None

        self.dots = []
        self._width = 0
        self._signals = []

#        self.connect('size-allocate', self._on_allocate)
        return

#    def _on_allocate(self, widget, allocation):
#        return

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

    def set_n_pages(self, n_pages, row_spacing=6):
        self.n_pages = n_pages
        self.clear_paging_dots()

        rowbox = gtk.HBox(spacing=row_spacing)
        row = gtk.Alignment(0.5, 0.5)
        row.add(rowbox)

        self.vbox.pack_start(row)

        max_w = self.allocation.width
        #print max_w, self.vbox.allocation.width
        w = 0
        for i in range(int(n_pages)):
            w += PagingDot.SIZE + 4

            if w > max_w:
                rowbox = gtk.HBox(spacing=row_spacing)
                row = gtk.Alignment(0.5, 0.5)
                row.add(rowbox)

                self.vbox.pack_start(row, expand=True)
                w = PagingDot.SIZE + row_spacing

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
        if not_overlapping(a, expose_area): return

        for dot in self.dots:
            dot.draw(cr, dot.allocation, expose_area, alpha)
        return


class PagingDot(LinkButton):

    SIZE =       max(8, int(0.6*EM+0.5))

    def __init__(self, page_number):
        LinkButton.__init__(self, None, None, None)
        self.set_size_request(-1, PagingDot.SIZE)
        self.is_selected = False
        self.page_number = page_number

        # a11y for page selector
        self.set_property("can-focus", True)
        self.a11y = self.get_accessible()
        self.a11y.set_name(_("Go to page %d") % (self.page_number + 1))
        return

    def calc_width(self):
        return PagingDot.SIZE

    def draw(self, cr, a, expose_area, alpha):
        cr.save()
        #cr.rectangle(a)
        #cr.clip()

        cr.save()
        cr.translate(0.5,0.5)
        cr.set_line_width(1)
        c = ShapeCircle()
        c.layout(cr, a.x, a.y, a.width-1, a.height-1)

        if self.is_selected:
            if self.state == gtk.STATE_PRELIGHT or self.has_focus():
                r,g,b = color_floats(self.style.dark[gtk.STATE_SELECTED])
            else:
                r,g,b = color_floats(self.style.dark[self.state])

            cr.set_source_rgba(r,g,b,alpha)
            cr.fill_preserve()
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_PRELIGHT or self.has_focus():
            r,g,b = color_floats(self.style.dark[gtk.STATE_SELECTED])
            cr.set_source_rgba(r,g,b,0.5)
            cr.fill_preserve()
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_NORMAL:
            r,g,b = color_floats(self.style.dark[self.state])
            cr.set_source_rgb(r,g,b)
            cr.stroke()

        elif self.state == gtk.STATE_ACTIVE:
            r,g,b = color_floats(self.style.dark[self.state])
            cr.set_source_rgb(r,g,b)
            cr.fill_preserve()
            cr.stroke()

        cr.restore()
        return
