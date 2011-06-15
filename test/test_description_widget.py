#!/usr/bin/python

import logging
import sys
import unittest

sys.path.insert(0,"../")
from softwarecenter.ui.gtk.widgets.description import AppDescription


class TestDescriptionWidget(unittest.TestCase):
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
                         


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
