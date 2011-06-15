#!/usr/bin/python

import apt
import logging
import sys
import unittest

sys.path.insert(0,"../")
from softwarecenter.ui.gtk.widgets.description import AppDescription


class TestAppDescriptionWidget(unittest.TestCase):
    """ tests the description widget """

    def test_description_parser_regression_test_moppet(self):
        app_description = AppDescription()
        # this is a regression test for the description parser
        # there is a bug that after GAME FEATURES the bullet list
        # is not actually displayed
        s = """A challenging 3D block puzzle game.

Puzzle Moppet is a challenging 3D puzzle game featuring a diminutive and apparently mute creature who is lost in a mysterious floating landscape.

GAME FEATURES
* Save the Moppet from itself
"""
        app_description.set_description(s, "test")
        description_text = []
        for p in app_description.description.order:
            description_text.append(p.get_text())
        self.assertEqual(
            description_text,
            ["A challenging 3D block puzzle game.",
             "Puzzle Moppet is a challenging 3D puzzle game featuring a diminutive and apparently mute creature who is lost in a mysterious floating landscape.",
             "GAME FEATURES",
             "Save the Moppet from itself",
             ])

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
        app_description = AppDescription()
        cache = apt.Cache()
        for pkg in cache:
            if pkg.candidate:
                # set description
                app_description.set_description(pkg.description,
                                                pkg.name)
                # gather the text in there
                description_processed = ""
                for p in app_description.description.order:
                    description_processed += p.get_text()
                self.assertEqual(descr_cmp_filter(pkg.description),
                                 descr_cmp_filter(description_processed),
                                 "pkg '%s' diverge:\n%s\n\n%s\n" % (
                        pkg.name,
                        descr_cmp_filter(pkg.description),
                        descr_cmp_filter(description_processed)))


        
                         


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
