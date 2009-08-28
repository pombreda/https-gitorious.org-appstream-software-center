import gobject
import gtk
import os
import glob


class AnimatedImage(gtk.Image):
    
    FPS = 12

    def __init__(self, globexp):
        super(AnimatedImage, self).__init__()
        self._progressN = 0
        self.images = sorted(glob.glob(globexp))
        self.set_from_file(self.images[self._progressN])
        source_id = gobject.timeout_add(1000/self.FPS, self.progressIconTimeout)

    def progressIconTimeout(self):
        self._progressN += 1
        if self._progressN == len(self.images):
            self._progressN = 0
        image.set_from_file(self.images[self._progressN])
        return True

if __name__ == "__main__":

    if os.path.exists("./data"):
        datadir = "./data/"
    else:
        datadir = "/usr/share/software-store/"

    image = AnimatedImage(datadir+"/icons/32x32/status/*.png")

    win = gtk.Window()
    win.add(image)
    win.set_size_request(400,400)
    win.show_all()

    gtk.main()

