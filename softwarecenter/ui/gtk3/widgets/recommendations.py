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

from gi.repository import Gtk, GObject
import logging

from gettext import gettext as _

from softwarecenter.ui.gtk3.em import StockEms
from softwarecenter.ui.gtk3.widgets.containers import (FramedHeaderBox,
                                                       FlowableGrid)
from softwarecenter.db.categories import (RecommendedForYouCategory,
                                          RecommendedForYouInCatCategory,
                                          AppRecommendationsCategory)
from softwarecenter.backend.recagent import RecommenderAgent
from softwarecenter.db.utils import get_installed_package_list
from softwarecenter.utils import get_uuid
from softwarecenter.config import get_config

LOG = logging.getLogger(__name__)

class RecommendationsPanel(FramedHeaderBox):
    """
    Base class for widgets that display recommendations
    """

    __gsignals__ = {
        "application-activated" : (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE, 
                                    (GObject.TYPE_PYOBJECT,),
                                   ),
        }

    def __init__(self, catview):
        FramedHeaderBox.__init__(self)
        # FIXME: we only need the catview for "add_titles_to_flowgrid"
        #        and "on_category_clicked" so we should be able to
        #        extract this to a "leaner" widget
        self.catview = catview
        self.recommender_uuid = ""
        self.catview.connect(
                    "application-activated", self._on_application_activated)
        self.recommender_agent = RecommenderAgent()
        
    def get_recommender_uuid(self):
        # FIXME: probs should just pass this on in instead of reading config
        recommender_uuid = ""
        config = get_config()
        if config.has_option("general", "recommender_uuid"):
            recommender_uuid = config.get("general",
                                           "recommender_uuid")
        return recommender_uuid

    def _on_application_activated(self, catview, app):
        self.emit("application-activated", app)

class RecommendationsPanelLobby(RecommendationsPanel):
    """
    Panel for use in the lobby view that manages the recommendations experience,
    includes the initial opt-in screen and display of recommendations once they
    have been received from the recommender agent
    """
    
    __gsignals__ = {
        "recommendations-opt-in" : (GObject.SIGNAL_RUN_LAST,
                                    GObject.TYPE_NONE, 
                                    (GObject.TYPE_STRING,),
                                   ),
        "recommendations-opt-out" : (GObject.SIGNAL_RUN_LAST,
                                     GObject.TYPE_NONE, 
                                     (),
                                    ),
        }
        
    def __init__(self, catview):
        RecommendationsPanel.__init__(self, catview)
        self.set_header_label(_(u"Recommended for You"))
        
        self.recommender_uuid = self.get_recommender_uuid()
        if not self.recommender_uuid:
            self._show_opt_in_view()
        else:
            self._update_recommended_for_you_content()
            
        self.add(self.recommended_for_you_content)

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
        # we upload the user profile here, and only after this is finished
        # do we fire the request for recommendations and finally display
        # them here -- a spinner is shown for this process (the spec
        # wants a progress bar, but we don't have access to real-time
        # progress info)
        self._upload_user_profile_and_get_recommendations()
        
    def _upload_user_profile_and_get_recommendations(self):
        # initiate upload of the user profile here
        self._upload_user_profile()
        
    def _upload_user_profile(self):
        self.spinner.set_text(_("Submitting inventory…"))
        self.show_spinner()
        self.recommender_uuid = get_uuid()
        installed_pkglist = list(get_installed_package_list())
        self.recommender_agent.connect("submit-profile",
                                  self._on_profile_submitted)
        self.recommender_agent.connect("error",
                                  self._on_profile_submitted_error)
        self.recommender_agent.query_submit_profile(
                self._generate_submit_profile_data(self.recommender_uuid, 
                                                   installed_pkglist))
                                                
    def _on_profile_submitted(self):
        # after the user profile data has been uploaded, make the request
        # and load the the recommended_for_you content
        LOG.debug("The recommendations profile has been successfully "
                  "submitted to the recommender agent")
        self.emit("recommendations-opt-in", self.recommender_uuid)
        self._update_recommended_for_you_content()
        
    def _on_profile_submitted_error(self, agent, msg):
        LOG.warn("Error while submitting the recommendations profile to the "
                 "recommender agent: %s" % msg)
        # TODO: handle this! display an error message in the panel
        self._hide_recommended_for_you_panel()
        
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
            self.header_implements_more_button()
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
            self._hide_recommended_for_you_panel()
        return
        
    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent for the "
                 "lobby recommendations: %s" % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_recommended_for_you_panel()

    def _hide_recommended_for_you_panel(self):
        # and hide the pane
        self.hide()
        
    def _generate_submit_profile_data(self,
                                      recommender_uuid,
                                      package_list):
        submit_profile_data = [
            {
                'uuid': recommender_uuid, 
                'package_list': package_list
            }
        ]
        return submit_profile_data
        
class RecommendationsPanelCategory(RecommendationsPanel):
    """
    Panel for use in the category view that displays recommended apps for
    the given category
    """
    def __init__(self, catview, category):
        RecommendationsPanel.__init__(self, catview)
        self.category = category
        self.set_header_label(_(u"Recommended for You in %s") % category.name)
        
        self.recommender_uuid = self.get_recommender_uuid()
        if self.recommender_uuid:
            self._update_recommended_for_you_in_cat_content()
            self.add(self.recommended_for_you_in_cat_content)
        else:
            self._hide_recommended_for_you_in_cat_panel()

    def _update_recommended_for_you_in_cat_content(self):
        self.recommended_for_you_in_cat_content = FlowableGrid()
        self.spinner.set_text(_("Receiving recommendations…"))
        self.show_spinner()
        # get the recommendations from the recommender agent
        self.recommended_for_you_cat = RecommendedForYouInCatCategory(
                                                            self.category)
        self.recommended_for_you_cat.connect(
                            'needs-refresh',
                            self._on_recommended_for_you_in_cat_agent_refresh)
        self.recommended_for_you_cat.connect('recommender-agent-error',
                                             self._on_recommender_agent_error)
        
    def _on_recommended_for_you_in_cat_agent_refresh(self, cat):
        docs = cat.get_documents(self.catview.db)
        print ">>> docs: ", docs
        # display the recommendedations
        if len(docs) > 0:
            self.header_implements_more_button()
            self.catview._add_tiles_to_flowgrid(
                                    docs,
                                    self.recommended_for_you_in_cat_content, 8)
            self.recommended_for_you_in_cat_content.show_all()
            self.show_content()
            self.more.connect('clicked',
                              self.catview.on_category_clicked,
                              cat)
        else:
            self._hide_recommended_for_you_in_cat_panel()
        return
        
    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent for the "
                 "lobby recommendations: %s" % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_recommended_for_you_in_cat_panel()

    def _hide_recommended_for_you_in_cat_panel(self):
        # and hide the pane
        self.hide()

        
class RecommendationsPanelDetails(RecommendationsPanel):
    """
    Panel for use in the details view to display recommendations for a given
    application
    """
    def __init__(self, catview):
        RecommendationsPanel.__init__(self, catview)
        self.set_header_label(_(u"People Also Installed"))
        self.app_recommendations_content = FlowableGrid()
        self.add(self.app_recommendations_content)
        
    def set_pkgname(self, pkgname):
        self.pkgname = pkgname
        self._update_app_recommendations_content()

    def _update_app_recommendations_content(self):
        self.app_recommendations_content.remove_all()
        self.spinner.set_text(_("Receiving recommendations…"))
        self.show_spinner()
        # get the recommendations from the recommender agent
        self.app_recommendations_cat = AppRecommendationsCategory(self.pkgname)
        self.app_recommendations_cat.connect(
                                    'needs-refresh',
                                    self._on_app_recommendations_agent_refresh)
        self.app_recommendations_cat.connect('recommender-agent-error',
                                             self._on_recommender_agent_error)
        
    def _on_app_recommendations_agent_refresh(self, cat):
        docs = cat.get_documents(self.catview.db)
        # display the recommendations
        if len(docs) > 0:
            self.catview._add_tiles_to_flowgrid(docs,
                                        self.app_recommendations_content, 8)
            self.app_recommendations_content.show_all()
            self.show_content()
        else:
            self._hide_app_recommendations_panel()
        return
        
    def _on_recommender_agent_error(self, agent, msg):
        LOG.warn("Error while accessing the recommender agent for the "
                 "details view recommendations: %s" % msg)
        # TODO: temporary, instead we will display cached recommendations here
        self._hide_app_recommendations_panel()

    def _hide_app_recommendations_panel(self):
        # and hide the pane
        self.hide()
    


def get_test_window_recommendations_panel_lobby():
    import softwarecenter.log
    softwarecenter.log.root.setLevel(level=logging.DEBUG)
    fmt = logging.Formatter("%(name)s - %(message)s", None)
    softwarecenter.log.handler.setFormatter(fmt)
    
    view = RecommendationsPanelLobby()

    win = Gtk.Window()
    win.connect("destroy", lambda x: Gtk.main_quit())
    win.add(view)
    win.set_data("rec_panel", view)
    win.set_size_request(600, 200)
    win.show_all()
    
    return win
    

if __name__ == "__main__":
    win = get_test_window_recommendations_panel_lobby()
    Gtk.main()
