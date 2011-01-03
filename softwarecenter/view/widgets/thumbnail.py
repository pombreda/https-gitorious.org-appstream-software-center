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
        self.loader.connect('url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('download-complete', self._on_screenshot_download_complete)

        self._build_ui()
        return

    def _build_ui(self):
        self.set_redraw_on_allocate(False)
        # the frame around the screenshot (placeholder)
        self.set_border_width(3)

        # eventbox so we can connect to event signals
        event = gtk.EventBox()
        event.set_visible_window(False)
        self.add(event)

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
        # 0.0 == left/top margin, 0.5 == center, 1.0 == right/bottom margin
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
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)

    # signal handlers
    def _on_enter(self, widget, event):
        if not self.get_is_actionable(): return

        self.window.set_cursor(gtk.gdk.Cursor(gtk.gdk.HAND2))
        if self._tip_fader: gobject.source_remove(self._tip_fader)
        self._tip_fader = gobject.timeout_add(25, self._tip_fade_in)
        return

    def _on_leave(self, widget, event):
        self.window.set_cursor(None)
        if self._tip_fader: gobject.source_remove(self._tip_fader)
        self._tip_fader = gobject.timeout_add(25, self._tip_fade_out)
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

            pb = self._downsize_pixbuf(self.screenshot_pixbuf, *self.MAX_SIZE)

            self.image.set_size_request(-1, -1)
            self.image.set_from_pixbuf(pb)
            # start the fade in
            gobject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        gobject.idle_add(setter_cb, screenshot_path)
        return

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and the download has completed """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):

        """ Configures the ScreenshotView depending on whether there is a screenshot available. """

        if not available:
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
            self.eventbox.remove(self.unavailable)
            self.eventbox.add(self.image)
            self.image.show()

        # set the loading animation (its a .gif so a our GtkImage happily renders the animation
        # without any fuss, NOTE this gif has a white background, i.e. it has no transparency
        # TODO: use a generic gtk.Spinner instead of this icon
        self.image.set_from_file(IMAGE_LOADING_INSTALLED)
        self.image.set_size_request(*self.IDLE_SIZE)
        self.set_size_request(250, -1)
        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its 
            reachable, if so it downloads the thumbnail.
            If not, it emits "image-url-reachable" False, then exits.
        """
        
        self.loader.begin_download(self.thumbnail_url)
        return

    def draw(self, cr, a, expose_area):
        """ Draws the thumbnail frame """

        if mkit.not_overlapping(a, expose_area): return

        if self.image.parent:
            ia = self.image.allocation
        else:
            ia = self.unavailable.allocation

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

