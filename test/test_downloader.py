#!/usr/bin/python

import glib
import os
import sys
import time
import unittest

sys.path.insert(0,"../")
from softwarecenter.utils import SimpleFileDownloader

class TestImageDownloader(unittest.TestCase):

    DOWNLOAD_FILENAME = "test_image_download"

    def setUp(self):
        self.downloader = SimpleFileDownloader()
        self.downloader.connect("file-url-reachable",
                                self._cb_image_url_reachable)
        self.downloader.connect("file-download-complete",
                                self._cb_image_download_complete)
        self._image_is_reachable = None
        self._image_downloaded_filename = None
        if os.path.exists(self.DOWNLOAD_FILENAME):
            os.unlink(self.DOWNLOAD_FILENAME)

    def _cb_image_url_reachable(self, downloader, is_reachable):
        self._image_is_reachable = is_reachable

    def _cb_image_download_complete(self, downloader, filename):
        self._image_downloaded_filename = filename

    def test_download_unreachable(self):
        self.downloader.download_file("http://examplex.com/not-there",
                                      self.DOWNLOAD_FILENAME)
        main_loop = glib.main_context_default()
        while self._image_is_reachable is None:
            while main_loop.pending():
                main_loop.iteration()
            time.sleep(0.1)
        self.assertNotEqual(self._image_is_reachable, None)
        self.assertFalse(self._image_is_reachable)
        self.assertTrue(not os.path.exists(self.DOWNLOAD_FILENAME))
 
    def test_download_reachable(self):
        self.downloader.download_file("http://www.ubuntu.com",
                                      self.DOWNLOAD_FILENAME)
        main_loop = glib.main_context_default()
        while self._image_downloaded_filename is None:
            while main_loop.pending():
                main_loop.iteration()
            time.sleep(0.1)
        self.assertNotEqual(self._image_is_reachable, None)
        self.assertTrue(self._image_is_reachable)
        self.assertTrue(os.path.exists(self.DOWNLOAD_FILENAME))

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
