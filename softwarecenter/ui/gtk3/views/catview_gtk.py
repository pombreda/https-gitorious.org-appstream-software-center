
from gi.repository import Gtk
from gi.repository import GObject
import logging
import xapian

from gettext import gettext as _

from appview import AppViewFilter
from softwarecenter.enums import NonAppVisibility
from softwarecenter.ui.gtk3.models.appstore2 import AppEnquire, AppPropertiesHelper
from softwarecenter.ui.gtk3.widgets.containers import *
from softwarecenter.ui.gtk3.widgets.buttons import (LabelTile,
                                                    CategoryTile,
                                                    FeaturedTile)
from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.db.categories import (Category,
                                          CategoriesParser,
                                          get_category_by_name,
                                          categories_sorted_by_name)

LOG_ALLOCATION = logging.getLogger("softwarecenter.ui.gtk.allocation")
LOG=logging.getLogger(__name__)


class CategoriesViewGtk(Gtk.Viewport, CategoriesParser):

    __gsignals__ = {
        "category-selected" : (GObject.SignalFlags.RUN_LAST,
                               None, 
                               (GObject.TYPE_PYOBJECT, ),
                              ),
                              
        "application-selected" : (GObject.SignalFlags.RUN_LAST,
                                  None,
                                  (GObject.TYPE_PYOBJECT, ),
                                 ),

        "application-activated" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (GObject.TYPE_PYOBJECT, ),
                                  ),
                                  
        "show-category-applist" : (GObject.SignalFlags.RUN_LAST,
                                   None,
                                   (),)
        }

    SPACING = PADDING = 3

    # art stuff
    STIPPLE = "softwarecenter/ui/gtk3/art/stipple.png"
    _asset_cache = {}


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
        icons - a Gtk.IconTheme
        apps_filter - ?
        apps_limit - the maximum amount of items to display to query for
        """

        self.cache = cache
        self.db = db
        self.icons = icons
        self.section = None

        Gtk.Viewport.__init__(self)
        CategoriesParser.__init__(self, db)
        self.set_shadow_type(Gtk.ShadowType.NONE)

        self.set_name("view")

        # setup base widgets
        # we have our own viewport so we know when the viewport grows/shrinks
        # setup widgets

        self.vbox = Gtk.VBox(spacing=3)
        self.add(self.vbox)

        # atk stuff
        atk_desc = self.get_accessible()
        atk_desc.set_name(_("Departments"))

        # appstore stuff
        self.categories = []
        self.header = ""
        self.apps_filter = apps_filter
        self.apps_limit = apps_limit

        # more stuff
        self._poster_sigs = []
        self._allocation = None

        self._cache_art_assets()
        self.vbox.connect("draw", self.on_draw, self._asset_cache)
        return

    def _cache_art_assets(self):
        import cairo

        assets = self._asset_cache
        # cache the bg pattern
        surf = cairo.ImageSurface.create_from_png(self.STIPPLE)
        ptrn = cairo.SurfacePattern(surf)
        ptrn.set_extend(cairo.EXTEND_REPEAT)
        assets["stipple"] = ptrn
        return

    def build(self, desktopdir):
        pass

    def on_draw(self, widget, cr, assets):
        cr.set_source(assets["stipple"])
        cr.paint()
        return

    #~ def _on_app_clicked(self, btn):
        #~ app = btn.app
        #~ appname = app[AppStore.COL_APP_NAME]
        #~ pkgname = app[AppStore.COL_PKGNAME]
        #~ rating = app[AppStore.COL_RATING]
        #~ self.emit("application-selected", Application(appname, pkgname, "", rating))
        #~ self.emit("application-activated", Application(appname, pkgname, "", rating))
        #~ return False

    def _on_category_clicked(self, cat_btn, cat):
        """emit the category-selected signal when a category was clicked"""
        LOG.debug("on_category_changed: %s" % cat.name)
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

        # this means that the departments don't jump down once the cache loads
        # it doesn't look odd if the recommends are never loaded
        #~ self.recommended = Gtk.Label()
        #~ self.vbox.pack_start(self.recommended, False, False, 0)

        self.build(desktopdir)
        return

    def _build_homepage_view(self):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        #~ self._append_recommendations()
        self._append_banner_ads()

        self.top_hbox = Gtk.HBox(spacing=self.SPACING)
        top_hbox_alignment = Gtk.Alignment()
        top_hbox_alignment.set_padding(0, 0, self.PADDING, self.PADDING)
        top_hbox_alignment.add(self.top_hbox)
        self.vbox.pack_start(top_hbox_alignment, False, False, 0)

        self._append_departments()

        self.right_column = Gtk.Box.new(Gtk.Orientation.VERTICAL, self.SPACING)
        self.top_hbox.pack_start(self.right_column, True, True, 0)

        self._append_featured()
        self._append_recommendations()

        self._append_video_clips()
        self._append_top_of_the_pops()
        return

    def _append_top_of_the_pops(self):
        self.totp_hbox = Gtk.HBox(spacing=self.SPACING)

        frame = FramedHeaderBox()
        frame.header_implements_more_button()
        frame.set_header_label(_("Most Popular"))

        label = Gtk.Label.new("Soda pop!!!")
        label.set_name("placeholder")
        label.set_size_request(-1, 200)

        frame.add(label)

        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, self.PADDING, 0)
        alignment.add(frame)
        self.totp_hbox.add(alignment)

        frame = FramedHeaderBox()
        frame.header_implements_more_button()
        frame.set_header_label(_("Top Rated"))

        label = Gtk.Label.new("Demos ftw(?)")
        label.set_name("placeholder")
        label.set_size_request(-1, 200)

        frame.add(label)

        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, self.PADDING, 0)
        alignment.add(frame)
        self.totp_hbox.add(alignment)

        self.vbox.pack_start(self.totp_hbox, False, False, 0)
        return

    def _append_video_clips(self):
        frame = FramedHeaderBox()
        frame.set_header_expand(False)
        frame.set_header_position(HeaderPosition.LEFT)
        frame.set_header_label(_("Latest Demo Videos"))

        label = Gtk.Label.new("Videos go here")
        label.set_name("placeholder")
        label.set_size_request(-1, 200)

        frame.add(label)

        alignment = Gtk.Alignment()
        alignment.set_padding(0, 0, self.PADDING, self.PADDING)
        alignment.add(frame)

        self.vbox.pack_start(alignment, False, False, 0)
        return

    def _append_banner_ads(self):
        placeholder = Gtk.Label.new("Banner Ad (Placeholder)")
        placeholder.set_size_request(-1, 200)
        placeholder.set_name("placeholder")
        self.vbox.pack_start(placeholder, False, False, 0)
        return

    def _append_departments(self):
        # set the departments section to use the label markup we have just defined
        cat_vbox = FramedBox(Gtk.Orientation.VERTICAL)
        self.top_hbox.pack_start(cat_vbox, False, False, 0)

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        mrkup = "<small>%s</small>"
        for cat in sorted_cats:
            if 'carousel-only' in cat.flags: continue
            category_name = mrkup % GObject.markup_escape_text(cat.name)
            label = LabelTile(category_name, None)
            label.label.set_alignment(0.0, 0.5)
            label.label.set_use_markup(True)
            label.connect('clicked', self._on_category_clicked, cat)
            cat_vbox.pack_start(label, False, False, 0)
        return

    def _append_featured(self):
        #~ featured_cat = get_category_by_name(self.categories, 
                                            #~ u"What\u2019s New")  # unstranslated name
        featured_cat = get_category_by_name(self.categories, 
                                            u"Featured")  # unstranslated name


        enq = AppEnquire(self.cache, self.db)
        app_filter = AppViewFilter(self.db, self.cache)
        enq.set_query(featured_cat.query,
                      limit=24,
                      filter=app_filter,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=False)

        self.featured = FlowableGrid()
        #~ self.featured.row_spacing = StockEms.SMALL
        frame = Frame()
        frame.set_corner_label(_("New"))
        frame.add(self.featured)
        self.right_column.pack_start(frame, True, True, 0)

        helper = AppPropertiesHelper(self.db, self.cache, self.icons)
        for doc in enq.get_documents()[15:21]:
            name = helper.get_appname(doc)
            icon_pb = helper.get_icon_at_size(doc, 48, 48)
            stats = helper.get_review_stats(doc)
            tile = FeaturedTile(name, icon_pb, stats)
            tile.connect('clicked', self._on_category_clicked, doc)
            self.featured.add_child(tile)
        return

    def _append_recommendations(self):
        featured_cat = get_category_by_name(self.categories, 
                                            u"Featured")  # unstranslated name

        enq = AppEnquire(self.cache, self.db)
        app_filter = AppViewFilter(self.db, self.cache)
        enq.set_query(featured_cat.query,
                      limit=6,
                      filter=app_filter,
                      nonapps_visible=NonAppVisibility.ALWAYS_VISIBLE,
                      nonblocking_load=False)

        self.featured = FlowableGrid()
        frame = FramedHeaderBox(Gtk.Orientation.VERTICAL)
        frame.add(self.featured)
        frame.set_header_label(_("Recommended For You"))
        frame.header_implements_more_button()
        self.right_column.pack_start(frame, True, True, 0)

        helper = AppPropertiesHelper(self.db, self.cache, self.icons)
        for doc in enq.get_documents():
            name = helper.get_appname(doc)
            icon_pb = helper.get_icon_at_size(doc, 48, 48)
            stats = helper.get_review_stats(doc)
            tile = FeaturedTile(name, icon_pb, stats)
            tile.connect('clicked', self._on_category_clicked, doc)
            self.featured.add_child(tile)
        return

    def build(self, desktopdir):
        self.categories = self.parse_applications_menu(desktopdir)
        self.header = _('Departments')
        self._build_homepage_view()
        self.show_all()
        return

    # stubs for the time being
    def stop_carousels(self):
        pass

    def start_carousels(self):
        pass


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
        self.current_category = None
        self.departments = None
        return

    def _append_subcat_departments(self, root_category, num_items):
        m = "<b><big>%s</big></b>"
        if self.departments is None:
            self.subcat_label = Gtk.Label()
            self.subcat_label.set_alignment(0, 0.5)

            self.departments = FlowableGrid(paint_grid_pattern=False)
            self.departments.set_row_spacing(6)
            self.departments.set_column_spacing(6)

            frame = FramedBox(spacing=StockEms.MEDIUM,
                              padding=StockEms.LARGE)
            # set x/y-alignment and x/y-expand
            frame.set(0.5, 0.0, 1.0, 1.0)

            frame.pack_start(self.subcat_label, False, False, 0)
            frame.pack_start(self.departments, True, True, 0)

            # append the departments section to the page
            self.vbox.pack_start(frame, True, True, 0)
        else:
            self.departments.remove_all()

        # set the subcat header
        self.subcat_label.set_markup(m % GObject.markup_escape_text(self.header))

        # sort Category.name's alphabetically
        sorted_cats = categories_sorted_by_name(self.categories)

        for cat in sorted_cats:
            # add the subcategory if and only if it is non-empty
            enquire = xapian.Enquire(self.db.xapiandb)
            enquire.set_query(cat.query)

            if len(enquire.get_mset(0,1)):
                tile = CategoryTile(cat.name, cat.iconname)
                tile.connect('clicked', self._on_category_clicked, cat)
                self.departments.add_child(tile)

        # partialy work around a (quite rare) corner case
        if num_items == 0:
            enquire = xapian.Enquire(self.db.xapiandb)
            enquire.set_query(xapian.Query(xapian.Query.OP_AND, 
                                           root_category.query,
                                           xapian.Query("ATapplication")))
            # assuming that we only want apps is not always correct ^^^
            tmp_matches = enquire.get_mset(0, len(self.db))#, None, self.apps_filter)
            num_items = tmp_matches.get_matches_estimated()

        # append an additional button to show all of the items in the category
        all_cat = Category("All", _("All"), "category-show-all", root_category.query)
        name = GObject.markup_escape_text('%s %s' % (_("All"), num_items))
        tile = CategoryTile(name, "category-show-all")
        tile.connect('clicked', self._on_category_clicked, all_cat)
        self.departments.add_child(tile)
        return

    def _build_subcat_view(self, root_category, num_items):
        # these methods add sections to the page
        # changing order of methods changes order that they appear in the page
        self._append_subcat_departments(root_category, num_items)
        self.show_all()
        return

    def set_subcategory(self, root_category, num_items=0, block=False):
        self.current_category = root_category
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


if __name__ == "__main__":
    import sys, os
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    from softwarecenter.db.pkginfo import get_pkg_info
    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    from softwarecenter.paths import ICON_PATH
    icons = Gtk.IconTheme.get_default()
    icons.append_search_path(ICON_PATH)
    icons.append_search_path(os.path.join(datadir,"icons"))
    icons.append_search_path(os.path.join(datadir,"emblems"))
    # HACK: make it more friendly for local installs (for mpt)
    icons.append_search_path(datadir+"/icons/32x32/status")
    # add the humanity icon theme to the iconpath, as not all icon 
    # themes contain all the icons we need
    # this *shouldn't* lead to any performance regressions
    path = '/usr/share/icons/Humanity'
    if os.path.exists(path):
        for subpath in os.listdir(path):
            subpath = os.path.join(path, subpath)
            if os.path.isdir(subpath):
                for subsubpath in os.listdir(subpath):
                    subsubpath = os.path.join(subpath, subsubpath)
                    if os.path.isdir(subsubpath):
                        icons.append_search_path(subsubpath)

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    apps_filter = AppViewFilter(db, cache)

    # gui
    win = Gtk.Window()
    n = Gtk.Notebook()

    from softwarecenter.paths import APP_INSTALL_PATH
    view = LobbyViewGtk(datadir, APP_INSTALL_PATH,
                        cache, db, distro,
                        icons, apps_filter)

    l = Gtk.Label()
    l.set_text("Lobby")

    scroll = Gtk.ScrolledWindow()
    scroll.add(view)
    n.append_page(scroll, l)

    # find a cat in the LobbyView that has subcategories
    subcat_cat = None
    for cat in view.categories:
        if cat.subcategories:
            subcat_cat = cat
            break

    view = SubCategoryViewGtk(datadir, APP_INSTALL_PATH,
                              cache, db, distro,
                              icons, apps_filter)

    view.set_subcategory(cat)

    l = Gtk.Label()
    l.set_text("Subcats")

    scroll = Gtk.ScrolledWindow()
    scroll.add(view)
    n.append_page(scroll, l)

    win.add(n)
    win.set_size_request(600,400)
    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    # run it
    Gtk.main()


