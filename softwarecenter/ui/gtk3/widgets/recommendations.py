# -*- coding: utf-8 -*-
# Copyright (C) 2012 Canonical
#
# Authors:
#  Gary Lasker
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

from gi.repository import Gtk
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.containers import (FramedHeaderBox,
                                                       FlowableGrid)

LOG = logging.getLogger(__name__)

class RecommendationsPanel(Gtk.Alignment):
    """
    Panel for use in the main view that manages the recommendations experience,
    includes the initial opt-in screen and display of recommendations once they
    have been received from the recommender agent
    """
    def __init__(self):
        Gtk.Alignment.__init__(self)
        self.hbox = Gtk.HBox(spacing=StockEms.SMALL)
        self.set_padding(0, 0, StockEms.MEDIUM-2, StockEms.MEDIUM-2)
        self.add(self.hbox)
        
        self.recommended_for_you = FlowableGrid()
        self.recommended_for_you_frame = FramedHeaderBox()
        self.recommended_for_you_frame.set_header_label(
                                                _(u"Recommended for You"))
        self.recommended_for_you_frame.add(self.recommended_for_you)
        self.recommended_for_you_frame.header_implements_more_button()
        self.hbox.pack_start(self.recommended_for_you_frame, True, True, 0)
        
    def update_recommended_for_you_content(self):
        self.recommended_for_you.remove_all()
        self.recommended_for_you_frame.show_spinner()



def get_test_window_recommendations_panel():
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)
    
    from softwarecenter.ui.gtk3.widgets.recommendations import RecommendationsPanel
    view = RecommendationsPanel()

    win = Gtk.Window()
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.add(view)
    win.set_size_request(800, 300)
    win.show_all()
    
    view.update_recommended_for_you_content()

    return win
    

if __name__ == "__main__":
    win = get_test_window()
    Gtk.main()
