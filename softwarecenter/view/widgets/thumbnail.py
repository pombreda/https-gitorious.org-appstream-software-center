import gtk
import gobject
import mkit
import pangocairo

from softwarecenter.enums import *
from softwarecenter.utils import SimpleFileDownloader, uri_to_filename

from imagedialog import ShowImageDialog

from gettext import gettext as _


class ScreenshotThumbnail(gtk.Alignment):

    """ Widget that displays screenshot availability, download prrogress,
        and eventually the screenshot itself.
    """

    MAX_SIZE = 225, 225
    IDLE_SIZE = 225, 150
    SPINNER_SIZE = 32, 32

    def __init__(self, distro, icons):
        gtk.Alignment.__init__(self, 0.5, 0.0)

        # data 
        self.distro = distro
        self.icons = icons

        self.appname = None
        self.thumb_url = None
        self.large_url = None

        # state tracking
        self.ready = False
        self.screenshot_pixbuf = None
        self.screenshot_available = False
        self.alpha = 0.0
        
        # tip stuff
        self.tip_alpha = 0.0
        self._tip_fader = 0
        self._tip_layout = self.create_pango_layout("")
        m = "<small><b>%s</b></small>"
        self._tip_layout.set_markup(m % _("Click for fullsize screenshot"))
        import pango
        self._tip_layout.set_ellipsize(pango.ELLIPSIZE_END)

        self._tip_xpadding = 4
        self._tip_ypadding = 1

        # cache the tip dimensions
        w, h = self._tip_layout.get_pixel_extents()[1][2:]
        self._tip_size = (w+2*self._tip_xpadding, h+2*self._tip_ypadding)

        # convienience class for handling the downloading (or not) of any screenshot
        self.loader = SimpleFileDownloader()
        self.loader.connect('file-url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('file-download-complete', self._on_screenshot_download_complete)

        self._build_ui()
        return

    def _build_ui(self):
        self.set_redraw_on_allocate(False)
        # the frame around the screenshot (placeholder)
        self.set_border_width(3)
        self.set_size_request(self.MAX_SIZE[0], -1)

        # eventbox so we can connect to event signals
        event = gtk.EventBox()
        event.set_visible_window(False)

        self.spinner_alignment = gtk.Alignment(0.5, 0.5)
        self.spinner_alignment.set_size_request(*self.IDLE_SIZE)

        self.spinner = gtk.Spinner()
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner_alignment.add(self.spinner)

        # the image
        self.image = gtk.Image()
        self.image.set_redraw_on_allocate(False)
        event.add(self.image)
        self.eventbox = event

        # connect the image to our custom draw func for fading in
        self.image.connect('expose-event', self._on_image_expose)

        # unavailable layout
        l = gtk.Label(_('No screenshot'))
        # force the label state to INSENSITIVE so we get the nice subtle etched in look
        l.set_state(gtk.STATE_INSENSITIVE)
        # center children both horizontally and vertically
        self.unavailable = gtk.Alignment(0.5, 0.5)
        self.unavailable.add(l)

        # set the widget to be reactive to events
        self.set_flags(gtk.CAN_FOCUS)
        event.set_events(gtk.gdk.BUTTON_PRESS_MASK|
                         gtk.gdk.BUTTON_RELEASE_MASK|
                         gtk.gdk.KEY_RELEASE_MASK|
                         gtk.gdk.KEY_PRESS_MASK|
                         gtk.gdk.ENTER_NOTIFY_MASK|
                         gtk.gdk.LEAVE_NOTIFY_MASK)

        # connect events to signal handlers
        event.connect('enter-notify-event', self._on_enter)
        event.connect('leave-notify-event', self._on_leave)
        event.connect('button-press-event', self._on_press)
        event.connect('button-release-event', self._on_release)

        self.connect('focus-in-event', self._on_focus_in)
#        self.connect('focus-out-event', self._on_focus_out)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)

    # signal handlers
    def _on_enter(self, widget, event):
        if not self.get_is_actionable(): return

        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        self.show_tip(hide_after=3000)
        return

    def _on_leave(self, widget, event):
        self.window.set_cursor(None)
        self.hide_tip()
        return

    def _on_press(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_release(self, widget, event):
        if event.button != 1 or not self.get_is_actionable(): return
        self.set_state(gtk.STATE_NORMAL)
        self._show_image_dialog()
        return

    def _on_focus_in(self, widget, event):
        self.show_tip(hide_after=3000)
        return

#    def _on_focus_out(self, widget, event):
#        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (gtk.keysyms.space, 
                            gtk.keysyms.Return, 
                            gtk.keysyms.KP_Enter) and self.get_is_actionable():
            self.set_state(gtk.STATE_ACTIVE)
        return

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (gtk.keysyms.space,
                            gtk.keysyms.Return, 
                            gtk.keysyms.KP_Enter) and self.get_is_actionable():
            self.set_state(gtk.STATE_NORMAL)
            self._show_image_dialog()
        return

    def _on_image_expose(self, widget, event):
        """ If the alpha value is less than 1, we override the normal draw
            for the GtkImage so we can draw with transparencey.
        """

        if widget.get_storage_type() != gtk.IMAGE_PIXBUF:
            return

        pb = widget.get_pixbuf()
        if not pb: return True

        a = widget.allocation
        cr = widget.window.cairo_create()

        cr.rectangle(a)
        cr.clip()

        # draw the pixbuf with the current alpha value
        cr.set_source_pixbuf(pb, a.x, a.y)
        cr.paint_with_alpha(self.alpha)
        
        if not self.tip_alpha: return True

        tw, th = self._tip_size
        if a.width > tw:
            self._tip_layout.set_width(-1)
        else:
            # tip is image width
            tw = a.width
            self._tip_layout.set_width(1024*(tw-2*self._tip_xpadding))

        tx, ty = a.x+a.width-tw, a.y+a.height-th

        rr = mkit.ShapeRoundedRectangleIrregular()
        rr.layout(cr, tx, ty, tx+tw, ty+th, radii=(6, 0, 0, 0))

        cr.set_source_rgba(0,0,0,0.85*self.tip_alpha)
        cr.fill()

        pcr = pangocairo.CairoContext(cr)
        pcr.move_to(tx+self._tip_xpadding, ty+self._tip_ypadding)
        pcr.layout_path(self._tip_layout)
        pcr.set_source_rgba(1,1,1,self.tip_alpha)
        pcr.fill()

        return True

    def _fade_in(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.alpha += 0.05
        if self.alpha >= 1.0:
            self.alpha = 1.0
            self.queue_draw()
            return False
        self.queue_draw()
        return True

    def _tip_fade_in(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.tip_alpha += 0.1
        ia = self.image.allocation
        tw, th = self._tip_size

        if self.tip_alpha >= 1.0:
            self.tip_alpha = 1.0
            self.image.queue_draw_area(ia.x+ia.width-tw,
                                       ia.y+ia.height-th,
                                       tw, th)
            return False

        self.image.queue_draw_area(ia.x+ia.width-tw,
                                   ia.y+ia.height-th,
                                   tw, th)
        return True

    def _tip_fade_out(self):
        """ This callback increments the alpha value from zero to 1,
            stopping once 1 is reached or exceeded.
        """

        self.tip_alpha -= 0.1
        ia = self.image.allocation
        tw, th = self._tip_size

        if self.tip_alpha <= 0.0:
            self.tip_alpha = 0.0
            self.image.queue_draw_area(ia.x+ia.width-tw,
                                       ia.y+ia.height-th,
                                       tw, th)
            return False
        self.image.queue_draw_area(ia.x+ia.width-tw,
                                   ia.y+ia.height-th,
                                   tw, th)
        return True

    def _show_image_dialog(self):
        """ Displays the large screenshot in a seperate dialog window """

        url = self.large_url
        title = _("%s - Screenshot") % self.appname
        d = ShowImageDialog(
            title, url,
            self.distro.IMAGE_FULL_MISSING,
            os.path.join(self.loader.tmpdir, uri_to_filename(url)))
        d.run()
        d.destroy()
        return

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable: self.ready = True
        return

    def _downsize_pixbuf(self, pb, target_w, target_h):
        w = pb.get_width()
        h = pb.get_height()

        if w > h:
            sf = float(target_w) / w
        else:
            sf = float(target_h) / h

        sw = int(w*sf)
        sh = int(h*sf)

        return pb.scale_simple(sw, sh, gtk.gdk.INTERP_BILINEAR)

    def _on_screenshot_download_complete(self, loader, screenshot_path):

        def setter_cb(path):
            try:
                self.screenshot_pixbuf = gtk.gdk.pixbuf_new_from_file(path)
                #pb = gtk.gdk.pixbuf_new_from_file(path)
            except Exception, e:
                LOG.warn('Screenshot downloaded but the file could not be opened.', e)
                return False

            # remove the spinner
            if self.spinner_alignment.parent:
                self.remove(self.spinner_alignment)

            pb = self._downsize_pixbuf(self.screenshot_pixbuf, *self.MAX_SIZE)

            if not self.eventbox.parent:
                self.add(self.eventbox)
                self.show_all()

            self.image.set_size_request(-1, -1)
            self.image.set_from_pixbuf(pb)

            # queue parent redraw if height of new pb is less than idle height
            if pb.get_height() < self.IDLE_SIZE[1]:
                if self.parent:
                    self.parent.queue_draw()

            # start the fade in
            gobject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        gobject.idle_add(setter_cb, screenshot_path)
        return

    def show_tip(self, hide_after=0):
        if not self.image.get_property('visible') or \
            self.tip_alpha >= 1.0: return

        if self._tip_fader: gobject.source_remove(self._tip_fader)
        self._tip_fader = gobject.timeout_add(25, self._tip_fade_in)

        if hide_after:
            gobject.timeout_add(hide_after, self.hide_tip)
        return

    def hide_tip(self):
        if not self.image.get_property('visible') or \
            self.tip_alpha <= 0.0: return

        if self._tip_fader: gobject.source_remove(self._tip_fader)
        self._tip_fader = gobject.timeout_add(25, self._tip_fade_out)
        return

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and the download has completed """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):

        """ Configures the ScreenshotView depending on whether there is a screenshot available. """

        if not available:
            self.remove(self.spinner_alignment)
            self.spinner.stop()

            if self.image.parent:
                self.eventbox.remove(self.image)
                self.eventbox.add(self.unavailable)
                # set the size of the unavailable placeholder
                # 160 pixels is the fixed width of the thumbnails
                self.unavailable.set_size_request(*self.IDLE_SIZE)
                self.unavailable.show_all()
                acc = self.get_accessible()
                acc.set_name(_('%s - No screenshot available') % self.appname)
        else:
            if self.unavailable.parent:
                self.eventbox.remove(self.unavailable)
                self.eventbox.add(self.image)
                self.image.show()
                acc = self.get_accessible()
                acc.set_name(_('%s - Screenshot') % self.appname)

        self.screenshot_available = available
        return
 
    def configure(self, app_details):

        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """

        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))

        self.clear()
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname
#        self.thumbnail_url = app_details.thumbnail
        self.thumbnail_url = app_details.screenshot
        self.large_url = app_details.screenshot
        return

    def clear(self):

        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """

        self.screenshot_available = True
        self.ready = False
        self.alpha = 0.0

        if self.unavailable.parent:
            self.remove(self.unavailable)

        if self.eventbox.parent:
            self.remove(self.eventbox)

        if not self.spinner_alignment.parent:
            self.add(self.spinner_alignment)

        self.spinner.start()
        self.show_all()
        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its 
            reachable, if so it downloads the thumbnail.
            If not, it emits "file-url-reachable" False, then exits.
        """
        
        self.loader.download_file(self.thumbnail_url)
        return

    def draw(self, cr, a, expose_area):
        """ Draws the thumbnail frame """

        if mkit.not_overlapping(a, expose_area): return

        if self.image.get_property('visible'):
            ia = self.image.allocation
        elif self.unavailable.get_property('visible'):
            ia = self.unavailable.allocation
        else:
            ia = self.spinner_alignment.allocation

        x = a.x + (a.width - ia.width)/2
        y = ia.y

        if self.has_focus() or self.state == gtk.STATE_ACTIVE:
            cr.rectangle(x-2, y-2, ia.width+4, ia.height+4)
            cr.set_source_rgb(1,1,1)
            cr.fill_preserve()
            if self.state == gtk.STATE_ACTIVE:
                color = mkit.floats_from_gdkcolor(self.style.mid[self.state])
            else:
                color = mkit.floats_from_gdkcolor(self.style.dark[gtk.STATE_SELECTED])
            cr.set_source_rgb(*color)
            cr.stroke()
        else:
            cr.rectangle(x-3, y-3, ia.width+6, ia.height+6)
            cr.set_source_rgb(1,1,1)
            cr.fill()
            cr.save()
            cr.translate(0.5, 0.5)
            cr.set_line_width(1)
            cr.rectangle(x-3, y-3, ia.width+5, ia.height+5)

            dark = mkit.floats_from_gdkcolor(self.style.dark[self.state])
            cr.set_source_rgb(*dark)
            cr.stroke()
            cr.restore()

        if not self.screenshot_available:
            cr.rectangle(x, y, ia.width, ia.height)
            cr.set_source_rgb(*mkit.floats_from_gdkcolor(self.style.bg[self.state]))
            cr.fill()
        return


if __name__ == '__main__':

    def testing_expose_handler(thumb, event):
        cr = thumb.window.cairo_create()
        thumb.draw(cr, thumb.allocation, event.area)
        del cr
        return

    import sys, logging
    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    from softwarecenter.apt.aptcache import AptCache
    cache = AptCache()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    db = StoreDatabase(pathname, cache)
    db.open()

    icons = gtk.icon_theme_get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    t = ScreenshotThumbnail(distro, icons)
    t.connect('expose-event', testing_expose_handler)

    w = gtk.Window()
    w.set_border_width(10)

    vb = gtk.VBox(spacing=6)
    w.add(vb)

    vb.pack_start(gtk.Button('A button for focus testing'))
    vb.pack_start(t)

    w.show_all()
    w.connect('destroy', gtk.main_quit)

    from softwarecenter.db.application import Application
    app_details = Application("Movie Player", "totem").get_details(db)
    t.configure(app_details)
    t.download_and_display()

    gtk.main()
