# Copyright (C) 2011 Canonical
#
# Authors:
#  Matthew McGowan
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Atk, Gio, GObject, GdkPixbuf

import logging
import os

from softwarecenter.db.pkginfo import get_pkg_info
from softwarecenter.utils import SimpleFileDownloader

from imagedialog import SimpleShowImageDialog

from gettext import gettext as _

LOG = logging.getLogger(__name__)



class ScreenshotData(GObject.GObject):

    __gsignals__ = {"screenshots-available" : (GObject.SIGNAL_RUN_FIRST,
                                               GObject.TYPE_NONE,
                                               (),),
                    }

    def __init__(self, app_details):
        GObject.GObject.__init__(self)
        self.app_details = app_details
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname
        self.app_details.connect(
            "screenshots-available", self._on_screenshots_available)
        self.app_details.query_multiple_screenshots()
        self.screenshots = []
        return

    def _on_screenshots_available(self, screenshot_data, screenshots):
        self.screenshots = screenshots
        self.emit("screenshots-available")

    def get_n_screenshots(self):
        return len(self.screenshots)

    def get_nth_large_screenshot(self, index):
        return self.screenshots[index]['large_image_url']

    def get_nth_small_screenshot(self, index):
        return self.screenshots[index]['small_image_url']


class ScreenshotWidget(Gtk.VBox):

    MAX_SIZE_CONSTRAINTS = 300, 250
    SPINNER_SIZE = 32, 32

    ZOOM_ICON = "stock_zoom-page"
    NOT_AVAILABLE_STRING = _('No screenshot available')

    USE_CACHING = True

    def __init__(self, distro, icons):
        Gtk.VBox.__init__(self)
        # data
        self.distro = distro
        self.icons = icons
        self.data = None

        # state tracking
        self.ready = False
        self.screenshot_pixbuf = None
        self.screenshot_available = False

        # zoom cursor
        try:
            zoom_pb = self.icons.load_icon(self.ZOOM_ICON, 22, 0)
            # FIXME
            self._zoom_cursor = Gdk.Cursor.new_from_pixbuf(
                                    Gdk.Display.get_default(),
                                    zoom_pb,
                                    0, 0)  # x, y
        except:
            self._zoom_cursor = None

        # convienience class for handling the downloading (or not) of any screenshot
        self.loader = SimpleFileDownloader()
        self.loader.connect('error', self._on_screenshot_load_error)
        self.loader.connect('file-url-reachable', self._on_screenshot_query_complete)
        self.loader.connect('file-download-complete', self._on_screenshot_download_complete)

        self._build_ui()
        return

    def _build_ui(self):
        # the frame around the screenshot (placeholder)
        self.set_border_width(3)
        self.screenshot = Gtk.VBox()
        self.pack_start(self.screenshot, False, False, 0)

        # eventbox so we can connect to event signals
        event = Gtk.EventBox()
        event.set_visible_window(False)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.screenshot.add(self.spinner)

        # the image
        self.image = Gtk.Image()
        event.add(self.image)
        self.eventbox = event
        self.screenshot.add(self.eventbox)

        # unavailable layout
        self.unavailable = Gtk.Label(label=self.NOT_AVAILABLE_STRING)
        self.unavailable.set_alignment(0.5, 0.5)
        # force the label state to INSENSITIVE so we get the nice subtle etched in look
        self.unavailable.set_state(Gtk.StateType.INSENSITIVE)
        self.screenshot.add(self.unavailable)
        self.show_all()

    def _on_screenshot_download_complete(self, loader, screenshot_path):
        try:
            self.screenshot_pixbuf = GdkPixbuf.Pixbuf.new_from_file(screenshot_path)
        except Exception, e:
            LOG.exception("Pixbuf.new_from_file() failed")
            self.loader.emit('error', GObject.GError, e)
            return False

        pb = self._downsize_pixbuf(self.screenshot_pixbuf, *self.MAX_SIZE_CONSTRAINTS)
        self.image.set_from_pixbuf(pb)
        self.ready = True

        self.display_image()
        return

    def _on_screenshot_load_error(self, loader, err_type, err_message):
        self.set_screenshot_available(False)
        self.ready = True
        return

    def _on_screenshot_query_complete(self, loader, reachable):
        self.set_screenshot_available(reachable)
        if not reachable:
            self.ready = True
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

        return pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)

    def download_and_display_from_url(self, url):
        self.loader.download_file(url, use_cache=self.USE_CACHING)
        return

    def clear(self):
        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """

        self.screenshot_available = True
        self.ready = False
        self.display_spinner()
        return

    def display_spinner(self):
        self.image.clear()
        self.eventbox.hide()
        self.unavailable.hide()
        self.spinner.show()
        self.screenshot.set_size_request(*self.MAX_SIZE_CONSTRAINTS)
        self.spinner.start()
        return

    def display_unavailable(self):
        self.spinner.hide()
        self.spinner.stop()
        self.unavailable.show()
        self.eventbox.hide()
        self.screenshot.set_size_request(*self.MAX_SIZE_CONSTRAINTS)

        acc = self.get_accessible()
        acc.set_name(self.NOT_AVAILABLE_STRING)
        acc.set_role(Atk.Role.LABEL)
        return

    def display_image(self):
        self.unavailable.hide()
        self.spinner.stop()
        self.spinner.hide()
        self.eventbox.show_all()
        if self.thumbnails.get_children():
            self.screenshot.set_size_request(-1, self.MAX_SIZE_CONSTRAINTS[1])
        else:
            self.screenshot.set_size_request(-1, -1)
        self.thumbnails.show()
        return

    def get_is_actionable(self):
        """ Returns true if there is a screenshot available and
            the download has completed
        """
        return self.screenshot_available and self.ready

    def set_screenshot_available(self, available):
        """ Configures the ScreenshotView depending on whether there
            is a screenshot available.
        """
        if not available:
            self.display_unavailable()
        elif available and self.unavailable.get_property("visible"):
            self.display_spinner()
        self.screenshot_available = available
        return


class ScreenshotGallery(ScreenshotWidget):

    """ Widget that displays screenshot availability, download prrogress,
        and eventually the screenshot itself.
    """

    def __init__(self, distro, icons):
        ScreenshotWidget.__init__(self, distro, icons)
        self._init_signals()
        self._thumbnail_sigs = []
        return

    def _build_ui(self):
        ScreenshotWidget._build_ui(self)
        self.thumbnails = ThumbnailGallery(self.distro, self.icons)
        self.thumbnails.set_margin_top(3)
        self.thumbnails.set_halign(Gtk.Align.CENTER)
        self.pack_end(self.thumbnails, False, False, 0)
        self.thumbnails.connect("thumb-selected", self.on_thumbnail_selected)
        self.show_all()
        return

    def _init_signals(self):
        # set the widget to be reactive to events
        self.set_property("can-focus", True)
        event = self.eventbox
        event.set_events(Gdk.EventMask.BUTTON_PRESS_MASK|
                         Gdk.EventMask.BUTTON_RELEASE_MASK|
                         Gdk.EventMask.KEY_RELEASE_MASK|
                         Gdk.EventMask.KEY_PRESS_MASK|
                         Gdk.EventMask.ENTER_NOTIFY_MASK|
                         Gdk.EventMask.LEAVE_NOTIFY_MASK)

        # connect events to signal handlers
        event.connect('enter-notify-event', self._on_enter)
        event.connect('leave-notify-event', self._on_leave)
        event.connect('button-press-event', self._on_press)
        event.connect('button-release-event', self._on_release)

        self.connect('focus-in-event', self._on_focus_in)
#        self.connect('focus-out-event', self._on_focus_out)
        self.connect("key-press-event", self._on_key_press)
        self.connect("key-release-event", self._on_key_release)
        return

    # signal handlers
    def _on_enter(self, widget, event):
        if not self.get_is_actionable(): return

        self.get_window().set_cursor(self._zoom_cursor)
        #~ self.show_tip(hide_after=3000)
        return

    def _on_leave(self, widget, event):
        self.get_window().set_cursor(None)
        #~ self.hide_tip()
        return

    def _on_press(self, widget, event):
        if event.button != 1 or not self.get_is_actionable():
            return
        self.set_state(Gtk.StateType.ACTIVE)
        return

    def _on_release(self, widget, event):
        if event.button != 1 or not self.get_is_actionable():
            return
        self.set_state(Gtk.StateType.NORMAL)
        self._show_image_dialog()
        return

    def _on_focus_in(self, widget, event):
        self.show_tip(hide_after=3000)
        return

    def _on_key_press(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (Gdk.KEY_space,
                            Gdk.KEY_Return,
                            Gdk.KEY_KP_Enter) and self.get_is_actionable():
            self.set_state(Gtk.StateType.ACTIVE)
        return

    def _on_key_release(self, widget, event):
        # react to spacebar, enter, numpad-enter
        if event.keyval in (Gdk.KEY_space,
                            Gdk.KEY_Return,
                            Gdk.KEY_KP_Enter) and self.get_is_actionable():
            self.set_state(Gtk.StateType.NORMAL)
            self._show_image_dialog()
        return

    def _show_image_dialog(self):
        """ Displays the large screenshot in a seperate dialog window """

        if self.data and self.screenshot_pixbuf:
            title = _("%s - Screenshot") % self.data.appname
            toplevel = self.get_toplevel()
            d = SimpleShowImageDialog(title, self.screenshot_pixbuf, toplevel)
            d.run()
            d.destroy()
        return

    def fetch_screenshots(self, app_details):
        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """
        self.clear()
        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))
        self.data = ScreenshotData(app_details)
        self.data.connect(
            "screenshots-available", self._on_screenshots_available)
        self.display_spinner()
        self.download_and_display_from_url(app_details.screenshot)
        return

    def _on_screenshots_available(self, screenshots):
        self.thumbnails.set_thumbnails_from_data(screenshots)
        if self.ready:
            self.screenshot.set_size_request(
                -1, ScreenshotWidget.MAX_SIZE_CONSTRAINTS[1])
        else:
            self.screenshot.set_size_request(*self.MAX_SIZE_CONSTRAINTS)

    def clear(self):
        self.thumbnails.clear()
        ScreenshotWidget.clear(self)

    def on_thumbnail_selected(self, gallery, id_):
        ScreenshotWidget.clear(self)
        large_url = self.data.get_nth_large_screenshot(id_)
        self.download_and_display_from_url(large_url)
        return

    def draw(self, widget, cr):
        """ Draws the thumbnail frame """
        return


class Thumbnail(Gtk.EventBox):

    def __init__(self, id_, url, cancellable=None):
        Gtk.EventBox.__init__(self)
        self.set_visible_window(False)
        self.set_can_focus(True)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK|
            Gdk.EventMask.BUTTON_RELEASE_MASK|
            Gdk.EventMask.KEY_RELEASE_MASK|
            Gdk.EventMask.KEY_PRESS_MASK)
            #~ Gdk.EventMask.ENTER_NOTIFY_MASK|
            #~ Gdk.EventMask.LEAVE_NOTIFY_MASK)
        #~ gfile = Gio.file_new_for_uri(url)
        #~ stream = gfile.read(cancellable)
        self.id_ = id_

        def download_complete_cb(loader, path):
            width, height = ThumbnailGallery.THUMBNAIL_SIZE_CONTRAINTS
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        path,
                        width, height,  # width, height constraints
                        True)  # respect image proportionality
            im = Gtk.Image.new_from_pixbuf(pixbuf)
            self.add(im)
            self.show_all()
            return

        loader = SimpleFileDownloader()
        loader.connect("file-download-complete", download_complete_cb)
        loader.download_file(url, use_cache=ScreenshotWidget.USE_CACHING)
        return

    def do_draw(self, cr):
        for child in self:
            self.propagate_draw(child, cr)

        state = self.get_state_flags()
        if (Gtk.StateFlags.SELECTED & state) > 0 or self.has_focus():
            a = self.get_allocation()
            #~ context = self.get_style_context()
            #~ context.save()
            #~ context.set_state(Gtk.StateFlags.NORMAL)
            #~ Gtk.render_frame(
                #~ context, cr,
                #~ 0, 0,
                #~ a.width,
                #~ a.height)
            #~ context.restore()
            cr.set_line_width(2)
            cr.rectangle(1, 1, a.width-2, a.height-2)
            cr.set_source_rgb(1,0,0)
            cr.stroke()
        return


class ThumbnailGallery(Gtk.HBox):

    __gsignals__ = {
        "thumb-selected": (GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_NONE,
                           (int,),),}

    THUMBNAIL_SIZE_CONTRAINTS = 100, 80
    THUMBNAIL_MAX_COUNT = 3


    def __init__(self, distro, icons):
        Gtk.HBox.__init__(self)
        self.set_spacing(3)
        self.distro = distro
        self.icons = icons
        self.cancel = Gio.Cancellable()

        self._prev = None
        self._handlers = []
        return

    def clear(self):
        self.cancel.cancel()
        self.cancel.reset()

        for sig in self._handlers:
            GObject.source_remove(sig)

        for child in self:
            child.destroy()
        return

    def set_thumbnails_from_data(self, data):
        self.clear()

        # if there are multiple screenshots
        n = data.get_n_screenshots()

        if n == 1:
            return

        # get a random selection of thumbnails from those avaialble
        import random
        seq = random.sample(
            range(n),
            min(n, ThumbnailGallery.THUMBNAIL_MAX_COUNT))

        seq.sort()

        for i in seq:
            url = data.get_nth_small_screenshot(i)
            self._create_thumbnail_for_url(i, url)

        # set first child to selected
        self._prev = self.get_children()[0]
        self._prev.set_state_flags(Gtk.StateFlags.SELECTED, False)

        self.show_all()
        return

    def _create_thumbnail_for_url(self, index, url):
        thumbnail = Thumbnail(index, url, self.cancel)
        self.pack_start(thumbnail, False, False, 0)
        sig = thumbnail.connect("button-release-event", self.on_release)
        self._handlers.append(sig)
        return

    def on_release(self, thumb, event):
        if self._prev is not None:
            self._prev.set_state_flags(Gtk.StateFlags.NORMAL, True)
        thumb.set_state_flags(Gtk.StateFlags.SELECTED, True)
        self._prev = thumb
        self.emit("thumb-selected", thumb.id_)


def get_test_screenshot_thumbnail_window():

    icons = Gtk.IconTheme.get_default()
    icons.append_search_path("/usr/share/app-install/icons/")

    import softwarecenter.distro
    distro = softwarecenter.distro.get_distro()

    win = Gtk.Window()
    win.set_border_width(10)

    t = ScreenshotGallery(distro, icons)
    t.connect('draw', t.draw)
    win.set_data("screenshot_thumbnail_widget", t)

    vb = Gtk.VBox(spacing=6)
    win.add(vb)

    b = Gtk.Button('A button for focus testing')
    vb.pack_start(b, True, True, 0)
    win.set_data("screenshot_button_widget", b)
    vb.pack_start(t, True, True, 0)

    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    return win

if __name__ == '__main__':

    app_n = 0

    def testing_cycle_apps(_, thumb, apps, db):
        global app_n
        d = apps[app_n].get_details(db)

        if app_n + 1 < len(apps):
            app_n += 1
        else:
            app_n = 0

        thumb.fetch_screenshots(d)
        return True

    logging.basicConfig(level=logging.DEBUG)

    cache = get_pkg_info()
    cache.open()

    from softwarecenter.db.database import StoreDatabase
    xapian_base_path = "/var/cache/software-center"
    pathname = os.path.join(xapian_base_path, "xapian")
    db = StoreDatabase(pathname, cache)
    db.open()

    w = get_test_screenshot_thumbnail_window()
    t = w.get_data("screenshot_thumbnail_widget")
    b = w.get_data("screenshot_button_widget")

    from softwarecenter.db.application import Application
    apps = [Application("Movie Player", "totem"),
            Application("Comix", "comix"),
            Application("Gimp", "gimp"),
            Application("ACE", "uace")]

    b.connect("clicked", testing_cycle_apps, t, apps, db)

    Gtk.main()
