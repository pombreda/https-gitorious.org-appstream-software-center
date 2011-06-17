#!/usr/bin/python

import apt
import logging
import sys
import unittest

sys.path.insert(0,"../")
from softwarecenter.utils import normalize_package_description


class TestAppDescriptionNormalize(unittest.TestCase):
    """ tests the description noramlization """

    def test_description_parser_regression_test_moppet(self):
        # this is a regression test for the description parser
        # there is a bug that after GAME FEATURES the bullet list
        # is not actually displayed
        s = """A challenging 3D block puzzle game.

Puzzle Moppet is a challenging 3D puzzle game featuring a diminutive and apparently mute creature who is lost in a mysterious floating landscape.

GAME FEATURES
* Save the Moppet from itself
"""
        description_text = normalize_package_description(s)
        self.assertEqual(
            description_text,
            """A challenging 3D block puzzle game.
Puzzle Moppet is a challenging 3D puzzle game featuring a diminutive and apparently mute creature who is lost in a mysterious floating landscape.
GAME FEATURES
* Save the Moppet from itself""")

    def test_description_parser_selected(self):
        cache = apt.Cache()
        self.assertEqual(
            normalize_package_description(cache["arista"].description),
            """Arista is a simple multimedia transcoder, it focuses on being easy to use by making complex task of encoding for various devices simple.
Users should pick an input and a target device, choose a file to save to and go. Features:
* Presets for iPod, computer, DVD player, PSP, Playstation 3, and more.
* Live preview to see encoded quality.
* Automatically discover available DVD media and Video 4 Linux (v4l) devices.
* Rip straight from DVD media easily (requires libdvdcss).
* Rip straight from v4l devices.
* Simple terminal client for scripting.
* Automatic preset updating.""")
        self.assertEqual(
            normalize_package_description(cache["aa3d"].description),
            """This program generates the well-known and popular random dot stereograms in ASCII art.
Features:
* High quality ASCII art stereogram rendering
* Highly configurable
* User friendly command line interface (including full online help)""")

    def test_description_parser_all(self):
        import re
        def descr_cmp_filter(s):
            new = s
            for k in [r"\n\s*- ", r"\n\s*\* ", r"\n\s*o ", 
                      # actually kill off all remaining whitespace
                      r"\s"]:
                new = re.sub(k, "", new)
            return new

        # test that all descriptions are parsable without failure
        cache = apt.Cache()
        for pkg in cache:
            if pkg.candidate:
                # gather the text in there
                description_processed = normalize_package_description(pkg.description)
                self.assertEqual(descr_cmp_filter(pkg.description),
                                 descr_cmp_filter(description_processed),
                                 "pkg '%s' diverge:\n%s\n\n%s\n" % (
                        pkg.name,
                        descr_cmp_filter(pkg.description),
                        descr_cmp_filter(description_processed)))


        
                         


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
