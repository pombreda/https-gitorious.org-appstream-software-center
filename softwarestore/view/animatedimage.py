# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#  Andrew Higginson (rugby471)
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 3 of the License, or (at your option) any later
# version.
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
        """
        super(AnimatedImage, self).__init__()
        self._progressN = 0
        self._imagefiles = sorted(glob.glob(globexp))
        self.images = []
        if not self._imagefiles:
            raise IOError, "no images for the animation found in '%s'" % globexp
        for f in self._imagefiles:
            self.images.append(gtk.gdk.pixbuf_new_from_file(f))
        self.set_from_pixbuf(self.images[self._progressN])
        self.connect("show", self.start)
        self.connect("hide", self.stop)

    def start(self, w):
        source_id = gobject.timeout_add(int(1000/self.FPS), 
                                              self._progress_timeout)
        self._run = True

    def stop(self, w):
        self._run = False

    def _progress_timeout(self):
        self._progressN += 1
        if self._progressN == len(self.images):
            self._progressN = 0
        self.set_from_pixbuf(self.images[self._progressN])
        return self._run

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        datadir = sys.argv[1]
    elif os.path.exists("./data"):
        datadir = "./data/"
    else:
        datadir = "/usr/share/software-store/"

    image = AnimatedImage(datadir+"/icons/32x32/status/softwarestore_progress_*.png")

    win = gtk.Window()
    win.add(image)
    win.set_size_request(400,400)
    win.show()
    gobject.timeout_add_seconds(1, image.show)
    gobject.timeout_add_seconds(5, image.hide)

    gtk.main()


