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
from softwarecenter.db.categories import RecommendedForYouCategory

LOG = logging.getLogger(__name__)

class RecommendationsPanel(FramedHeaderBox):
    """
    Panel for use in the main view that manages the recommendations experience,
    includes the initial opt-in screen and display of recommendations once they
    have been received from the recommender agent
    """
    def __init__(self, catview):
        FramedHeaderBox.__init__(self)
        self.catview = catview
        self.set_header_label(_(u"Recommended for You"))
                
        if not self._is_opted_in():
            self._show_opt_in_view()
        else:
            self._update_recommended_for_you_content()
            
        self.add(self.recommended_for_you_content)
        self.header_implements_more_button()
        
    def _show_opt_in_view(self):
        self.opt_in_vbox = Gtk.VBox(spacing=12)
        self.opt_in_button = Gtk.Button()
        opt_in_button_label = Gtk.Label()
        opt_in_button_label.set_markup('<big>%s</big>' % _("Turn On Recommendations"))
        opt_in_button_label.set_padding(StockEms.SMALL, StockEms.SMALL)
        self.opt_in_button.add(opt_in_button_label)
        self.opt_in_button.connect("clicked", self._on_opt_in_button_clicked)
        opt_in_button_hbox = Gtk.HBox()
        opt_in_button_hbox.pack_start(self.opt_in_button, False, False, 0)
        opt_in_text = _("To make recommendations, Ubuntu Software Center "
                        "will occasionally send to Canonical an anonymous list "
                        "of software currently installed.")
        opt_in_label = Gtk.Label()
        opt_in_label.set_markup('<big>%s</big>' % opt_in_text)
        opt_in_label.set_use_markup(True)
        self.opt_in_vbox.pack_start(opt_in_button_hbox, False, False, 0)
        self.opt_in_vbox.pack_start(opt_in_label, False, False, 10)
        self.recommended_for_you_content = Gtk.Alignment.new(0.5, 0.5, 1.0, 1.0)
        self.recommended_for_you_content.set_padding(50, 50, 50, 50)
        self.recommended_for_you_content.add(self.opt_in_vbox)
        
    def _on_opt_in_button_clicked(self, button):
        # TODO: we upload the user profile here, and only after this is finished
        #       do we fire the request for recommendations and finally display
        #       them here -- a spinner is shown for this process (the spec
        #       wants a progress bar, but we don't have access to real-time
        #       progress info)
        # TODO: set and persist the opt-in state
        self._upload_user_profile_and_get_recommendations()
        
    def _upload_user_profile_and_get_recommendations(self):
        # initiate upload of the user profile here
        self._upload_user_profile()
        # after the user profile data has been uploaded, make the request
        # and load the the recommended_for_you content
        self._update_recommended_for_you_content()
        
    def _upload_user_profile(self):
        self.spinner.set_text(_("Submitting inventory…"))
        self.show_spinner()
        
    def _update_recommended_for_you_content(self):
        self.recommended_for_you_content = FlowableGrid()
        self.spinner.set_text(_("Receiving recommendations…"))
        self.show_spinner()
        # get the recommendations from the recommender agent
        self.recommended_for_you_cat = RecommendedForYouCategory()
        self.recommended_for_you_cat.connect(
                                    'needs-refresh',
                                    self._on_recommended_for_you_agent_refresh)
        self.recommended_for_you_cat.connect('recommender-agent-error',
                                             self._on_recommender_agent_error)
        
    def _on_recommended_for_you_agent_refresh(self, cat):
        docs = cat.get_documents(self.catview.db)
        # display the recommendedations
        if len(docs) > 0:
            self.catview._add_tiles_to_flowgrid(docs,
                                        self.recommended_for_you_content, 8)
            self.recommended_for_you_content.show_all()
            self.show_content()
            self.more.connect('clicked',
                              self.catview.on_category_clicked,
                              cat)
        else:
            # TODO: this test for zero docs is temporary and will not be
            # needed once the recommendation agent is up and running
            self._hide_recommended_for_you()
        return
        
    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent: %s" 
                                                            % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_recommended_for_you_panel()

    def _hide_recommended_for_you_panel(self):
        # and hide the pane
        self.hide()

    def _is_opted_in(self):
        ''' Return True if the user has opted in to the recommendations service
        '''
        # TODO: Implement this (persist the state, or the uuid)
        return False



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
    win.set_data("rec_panel", view)
    win.set_size_request(600, 200)
    win.show_all()
    
    return win
    

if __name__ == "__main__":
    win = get_test_window_recommendations_panel()
    Gtk.main()
