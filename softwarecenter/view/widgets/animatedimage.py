# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
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

import gobject
import gtk
import os
import glob
import time

class AnimatedImage(gtk.Image):
    
    FPS = 20.0

    def __init__(self, globexp):
        """ Animate a gtk.Image
    
        Keywords:
        globexp: pass a glob expression that is used for the animated images
                 (it can also be a gtk.gdk.Pixbuf if you require a static image)
        """
        super(AnimatedImage, self).__init__()
        self._progressN = 0
        if isinstance(globexp, gtk.gdk.Pixbuf):
            self.images = [globexp]
            self.set_from_pixbuf(globexp)
        elif isinstance(globexp, str):
            self._imagefiles = sorted(glob.glob(globexp))
            self.images = []
            if not self._imagefiles:
                raise IOError, "no images for the animation found in '%s'" % globexp
            for f in self._imagefiles:
                self.images.append(gtk.gdk.pixbuf_new_from_file(f))
            self.set_from_pixbuf(self.images[self._progressN])
            self.connect("show", self.start)
            self.connect("hide", self.stop)
        else:
            raise IOError, "need a glob expression or a pixbuf"

    def start(self, w=None):
        source_id = gobject.timeout_add(int(1000/self.FPS), 
                                              self._progress_timeout)
        self._run = True

    def stop(self, w=None):
        self._run = False

    def get_current_pixbuf(self):
        return self.images[self._progressN]

    def get_animation_len(self):
        return len(self.images)

    def _progress_timeout(self):
        self._progressN += 1
        if self._progressN == len(self.images):
            self._progressN = 0
        self.set_from_pixbuf(self.get_current_pixbuf())
        return self._run

class CellRendererAnimatedImage(gtk.CellRendererPixbuf):

    __gproperties__  = { 
        "image" : (gobject.TYPE_OBJECT, 
                   "Image",
                   "Image", 
                   gobject.PARAM_READWRITE),
    }
    FPS = 20.0

    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def _animation_helper(self, widget, image):
        #print time.time()
        for row in widget.get_model():
            cell_area = widget.get_cell_area(row.path, widget.get_column(0))
            widget.queue_draw_area(cell_area.x, cell_area.y, 
                                   cell_area.width, cell_area.height)
    def do_render(self, window, widget, background_area, cell_area, expose_area, flags):
        image = self.get_property("image")
        if image.get_animation_len() > 1:
            gobject.timeout_add(int(1000.0/self.FPS), self._animation_helper, widget, image)
        self.set_property("pixbuf", image.get_current_pixbuf())
        return gtk.CellRendererPixbuf.do_render(self, window, widget, background_area, cell_area, expose_area, flags)
    def do_get_size(self, widget, cell_area):
        image = self.get_property("image")
        self.set_property("pixbuf", image.get_current_pixbuf())
        return gtk.CellRendererPixbuf.do_get_size(self, widget, cell_area)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data"
    else:
        datadir = "/usr/share/software-center"

    image = AnimatedImage(datadir+"/icons/32x32/status/software-center-progress-*.png")
    image1 = AnimatedImage(datadir+"/icons/32x32/status/software-center-progress-*.png")
    image1.start()
    image2 = AnimatedImage(datadir+"/icons/32x32/status/software-center-progress-01.png")
    pixbuf = gtk.gdk.pixbuf_new_from_file(datadir+"/icons/32x32/status/software-center-progress-07.png")
    image3 = AnimatedImage(pixbuf)
    image3.show()

    model = gtk.ListStore(AnimatedImage)
    model.append([image1])
    model.append([image2])
    treeview = gtk.TreeView(model)
    tp = CellRendererAnimatedImage()
    column = gtk.TreeViewColumn("Icon", tp, image=0)
    treeview.append_column(column)
    treeview.show()

    box = gtk.VBox()
    box.pack_start(image)
    box.pack_start(image3)
    box.pack_start(treeview)
    box.show()
    win = gtk.Window()
    win.add(box)
    win.set_size_request(400,400)
    win.show()

    print "running the image for 5s"
    gobject.timeout_add_seconds(1, image.show)
    gobject.timeout_add_seconds(5, image.hide)

    gtk.main()


