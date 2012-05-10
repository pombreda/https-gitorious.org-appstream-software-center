#!/usr/bin/python

import datetime
import glob
import multiprocessing
import os
import subprocess
import tempfile
import time
import unittest

from testutils import setup_test_env
setup_test_env()
from softwarecenter.testutils import do_events


class TestLogging(unittest.TestCase):
    """ tests the sc logging facilities """

    def test_no_write_access_for_cache_dir(self):
        """ test for bug LP: #688682 """
        # make the test cache dir non-writeable
        import softwarecenter.paths
        cache_dir = softwarecenter.paths.SOFTWARE_CENTER_CACHE_DIR
        os.chmod(cache_dir, 600)
        self.assertFalse(os.access(cache_dir, os.W_OK))
        # and then start up the logger
        import softwarecenter.log
        self.assertTrue(os.path.exists(cache_dir + ".0"))
        self.assertFalse(os.path.exists(cache_dir + ".1"))
        self.assertTrue(os.path.exists(cache_dir))


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
