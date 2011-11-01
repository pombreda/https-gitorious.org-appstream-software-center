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



class ScreenshotData(object):

    def __init__(self, app_details):
        self.app_details = app_details
        self.appname = app_details.display_name
        self.pkgname = app_details.pkgname
        self.screenshots = self.app_details.screenshots
        return

    def get_n_screenshots(self):
        return len(self.screenshots)

    def get_nth_large_screenshot(self, index):
        return self.screenshots[index]['large_image_url']

    def get_nth_small_screenshot(self, index):
        return self.screenshots[index]['small_image_url']


class ScreenshotWidget(Gtk.VBox):

    MAX_SIZE = 300, 300
    IDLE_SIZE = 300, 150
    SPINNER_SIZE = 32, 32

    MAX_THUMBNAIL_COUNT = 3

    ZOOM_ICON = "stock_zoom-page"
    NOT_AVAILABLE_STRING = _('No screenshot available')

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
                                    0, 0)   # x, y
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

        self.vbox = Gtk.VBox(spacing=4)
        self.add(self.vbox)

        # eventbox so we can connect to event signals
        event = Gtk.EventBox()
        event.set_visible_window(False)

        self.spinner_alignment = Gtk.Alignment.new(0.5, 0.5, 1.0, 0.0)

        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner_alignment.add(self.spinner)

        # the image
        self.image = Gtk.Image()
        self.image.set_redraw_on_allocate(False)
        event.add(self.image)
        self.eventbox = event

        # unavailable layout
        l = Gtk.Label(label=self.NOT_AVAILABLE_STRING)
        # force the label state to INSENSITIVE so we get the nice subtle etched in look
        l.set_state(Gtk.StateType.INSENSITIVE)
        # center children both horizontally and vertically
        self.unavailable = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        self.unavailable.add(l)

    def _on_screenshot_download_complete(self, loader, screenshot_path):

        def setter_cb(path):
            try:
                self.screenshot_pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            except Exception, e:
                LOG.exception("Pixbuf.new_from_file() failed")
                self.loader.emit('error', GObject.GError, e)
                return False

            # remove the spinner
            if self.spinner_alignment.get_parent():
                self.spinner.stop()
                self.spinner.hide()
                self.vbox.remove(self.spinner_alignment)

            pb = self._downsize_pixbuf(self.screenshot_pixbuf, *self.MAX_SIZE)

            if not self.eventbox.get_parent():
                self.vbox.add(self.eventbox)
                if self.get_property("visible"):
                    self.show_all()

            self.image.set_size_request(-1, -1)
            self.image.set_from_pixbuf(pb)

            # start the fade in
            #~ GObject.timeout_add(50, self._fade_in)
            self.ready = True
            return False

        setter_cb(screenshot_path)
        #~ GObject.timeout_add(500, setter_cb, screenshot_path)
        return

    def _on_screenshot_load_error(self, loader, err_type, err_message):
        self.set_screenshot_available(False)
        self.ready = True
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

        return pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)

    def download_and_display_from_url(self, url):
        self.loader.download_file(url, use_cache=True)

        # show it
        if self.get_property('visible'):
            self.show_all()
        return

    def clear(self):
        """ All state trackers are set to their intitial states, and
            the old screenshot is cleared from the view.
        """

        self.screenshot_available = True
        self.ready = False

        if self.eventbox.get_parent():
            self.eventbox.hide()
            self.vbox.remove(self.eventbox)

        if not self.spinner_alignment.get_parent():
            self.vbox.add(self.spinner_alignment)

        self.spinner_alignment.set_size_request(*self.IDLE_SIZE)
        self.spinner.set_size_request(*self.SPINNER_SIZE)
        self.spinner.start()
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
            if not self.eventbox.get_parent():
                self.vbox.remove(self.spinner_alignment)
                self.spinner.stop()
                self.vbox.add(self.eventbox)

            if self.image.get_parent():
                self.image.hide()
                self.eventbox.remove(self.image)
                self.eventbox.add(self.unavailable)
                # set the size of the unavailable placeholder
                # 160 pixels is the fixed width of the thumbnails
                self.unavailable.set_size_request(*self.IDLE_SIZE)

            acc = self.get_accessible()
            acc.set_name(self.NOT_AVAILABLE_STRING)
            acc.set_role(Atk.Role.LABEL)
        else:
            if self.unavailable.get_parent():
                self.unavailable.hide()
                self.eventbox.remove(self.unavailable)
                self.eventbox.add(self.image)

            acc = self.get_accessible()
            acc.set_name(_('Screenshot'))
            acc.set_role(Atk.Role.PUSH_BUTTON)

        if self.get_property("visible"):
            self.show_all()
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
        self.thumbnails.set_halign(Gtk.Align.CENTER)
        self.vbox.pack_end(self.thumbnails, False, False, 0)
        self.thumbnails.connect("thumb-selected", self.on_thumbnail_selected)
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

    def configure(self, app_details):
        """ Called to configure the screenshotview for a new application.
            The existing screenshot is cleared and the process of fetching a
            new screenshot is instigated.
        """
        acc = self.get_accessible()
        acc.set_name(_('Fetching screenshot ...'))
        self.clear()
        self.data = ScreenshotData(app_details)
        return

    def clear(self):
        self.thumbnails.clear()
        ScreenshotWidget.clear(self)

    def on_thumbnail_selected(self, gallery, id_):
        ScreenshotWidget.clear(self)
        large_url = self.data.get_nth_large_screenshot(id_)
        self.download_and_display_from_url(large_url)
        return

    def download_and_display(self):
        """ Download then displays the screenshot.
            This actually does a query on the URL first to check if its
            reachable, if so it downloads the thumbnail.
            If not, it emits "file-url-reachable" False, then exits.
        """

        if self.data.get_n_screenshots() == 0:
            self.set_screenshot_available(False)
            return

        self.thumbnails.set_thumbnails_from_data(self.data)

        first = self.data.get_nth_large_screenshot(0)
        self.download_and_display_from_url(first)
        return

    def draw(self, widget, cr):
        """ Draws the thumbnail frame """
        return


class Thumbnail(Gtk.EventBox):

    def __init__(self, id_, url, cancellable):
        Gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        gfile = Gio.file_new_for_uri(url)
        stream = gfile.read(cancellable)
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream_at_scale(
                    stream,
                    80, 80,  # width, height constraints
                    True,  # respect image proportionality
                    None)  # error handler

        im = Gtk.Image.new_from_pixbuf(pixbuf)
        im.set_margin_left(2)
        im.set_margin_right(2)
        im.set_margin_top(2)
        im.set_margin_bottom(2)
        self.add(im)
        self.id_ = id_
        self.set_property("can-focus", True)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK|
            Gdk.EventMask.BUTTON_RELEASE_MASK)#|
            #~ Gdk.EventMask.KEY_RELEASE_MASK|
            #~ Gdk.EventMask.KEY_PRESS_MASK|
            #~ Gdk.EventMask.ENTER_NOTIFY_MASK|
            #~ Gdk.EventMask.LEAVE_NOTIFY_MASK)
        return


class ThumbnailGallery(Gtk.HBox):

    __gsignals__ = {
        "thumb-selected": (GObject.SIGNAL_RUN_LAST,
                           GObject.TYPE_NONE,
                           (int,),),}

    def __init__(self, distro, icons):
        Gtk.HBox.__init__(self)
        self.set_spacing(3)
        self.distro = distro
        self.icons = icons
        self.cancel = Gio.Cancellable()

        self._handlers = []
        return

    def clear(self):
        for sig in self._handlers:
            GObject.source_remove(sig)

        for child in self:
            child.destroy()
        return

    def set_thumbnails_from_data(self, data):
        self.cancel.cancel()
        self.cancel.reset()

        def work():
            # if there are multiple screenshots
            n = data.get_n_screenshots()
            if n > 1:
                # get a random selection of thumbnails from those avaialble
                import random
                seq = random.sample(
                    range(n),
                    min(n, ScreenshotWidget.MAX_THUMBNAIL_COUNT))

                seq.sort()

                for i in seq:
                    url = data.get_nth_small_screenshot(i)
                    self._create_thumbnail_for_url(i, url)

            self.show_all()
            return False

        GObject.idle_add(work)
        return

    def _create_thumbnail_for_url(self, index, url):
        thumbnail = Thumbnail(index, url, self.cancel)
        self.pack_start(thumbnail, False, False, 0)
        sig = thumbnail.connect("button-release-event", self.on_release)
        self._handlers.append(sig)
        return

    def on_release(self, thumb, event):
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

    vb.pack_start(Gtk.Button('A button for focus testing'), True, True, 0)
    vb.pack_start(t, True, True, 0)

    win.show_all()
    win.connect('destroy', Gtk.main_quit)

    from mock import Mock
    app_details = Mock()
    app_details.display_name = "display name"
    app_details.pkgname = "pkgname"

    url = "http://www.ubuntu.com/sites/default/themes/ubuntu10/images/footer_logo.png"
    app_details.thumbnail = url
    app_details.screenshot = url
    app_details.screenshots = [
        {'small_image_url': url,
         'large_image_url': url,
         'version': 1},]

    t.configure(app_details)
    t.download_and_display()

    return win

if __name__ == '__main__':

    app_n = 0

    def testing_cycle_apps(thumb, apps, db):
        global app_n
        d = apps[app_n].get_details(db)

        if app_n + 1 < len(apps):
            app_n += 1
        else:
            app_n = 0

        thumb.configure(d)
        thumb.download_and_display()
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

    from softwarecenter.db.application import Application
    apps = [Application("Movie Player", "totem"),
            Application("Gimp", "gimp"),
            Application("ACE", "uace")]

    GObject.timeout_add_seconds(6, testing_cycle_apps, t, apps, db)

    Gtk.main()
