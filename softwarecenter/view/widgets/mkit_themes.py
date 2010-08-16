# Copyright (C) 2010 Matthew McGowan
#
# Authors:
#   Matthew McGowan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import gtk
import colorsys

import logging

THEME_MESSAGE_DISPLAYED = False

class ColorArray:

    def __init__(self, color_array=None):
        self.color_array = {}
        if not color_array: return
        for state in (gtk.STATE_NORMAL, gtk.STATE_ACTIVE, gtk.STATE_SELECTED, \
            gtk.STATE_PRELIGHT, gtk.STATE_INSENSITIVE):
            self.color_array[state] = color_from_gdkcolor(color_array[state])
        return

    def set_color_array(self, normal, active, prelight, selected, insensitive):
        self.color_array[gtk.STATE_NORMAL] = normal
        self.color_array[gtk.STATE_ACTIVE] = active
        self.color_array[gtk.STATE_SELECTED] = selected
        self.color_array[gtk.STATE_PRELIGHT] = prelight
        self.color_array[gtk.STATE_INSENSITIVE] = insensitive
        return

    def __getitem__(self, state):
        return self.color_array[state]


class Color:

    def __init__(self, red, green, blue):
        self.red = red
        self.green = green
        self.blue = blue
        return

    def floats(self):
        return self.red, self.green, self.blue

    def gdkcolor(self):
        r,g,b = self.floats()
        return gtk.gdk.Color(int(r*65535), int(g*65535), int(b*65535))

    def lighten(self):
        return self.shade(1.3)

    def darken(self):
        return self.shade(0.7)

    def shade(self, factor):
        # as seen in clutter-color.c
        h,l,s = colorsys.rgb_to_hls(*self.floats())

        l *= factor
        if l > 1.0:
            l = 1.0
        elif l < 0:
            l = 0

        s *= factor
        if s > 1.0:
            s = 1.0
        elif s < 0:
            s = 0

        r,g,b = colorsys.hls_to_rgb(h,l,s)
        return Color(r,g,b)

    def mix(self, color2, mix_factor):
        # as seen in Murrine's cairo-support.c
        r1, g1, b1 = self.floats()
        r2, g2, b2 = color2.floats()
        r = r1*(1-mix_factor)+r2*mix_factor
        g = g1*(1-mix_factor)+g2*mix_factor
        b = b1*(1-mix_factor)+b2*mix_factor
        return Color(r,g,b)


# Theme base class with common methods
class Theme:

    def build_palette(self, gtksettings):
        style = gtk.rc_get_style_by_paths(gtksettings,
                                          'GtkWindow',
                                          'GtkWindow',
                                          gtk.Window)

        style = style or gtk.widget_get_default_style()
        
        # build pathbar color palette
        self.fg =    ColorArray(style.fg)
        self.bg =    ColorArray(style.bg)
        self.text =  ColorArray(style.text)
        self.base =  ColorArray(style.base)
        self.light = ColorArray(style.light)
        self.mid =   ColorArray(style.mid)
        self.dark =  ColorArray(style.dark)
        return


class Human(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2.5,
            'min-part-width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow-width': 13,
            'scroll-duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override-base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:  (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                       self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:   (self.bg[gtk.STATE_NORMAL].shade(1.00),
                                       self.bg[gtk.STATE_NORMAL].shade(0.75)),

                  gtk.STATE_SELECTED: (self.bg[gtk.STATE_NORMAL].shade(1.11),
                                       self.bg[gtk.STATE_NORMAL]),

                  gtk.STATE_PRELIGHT: (self.bg[gtk.STATE_NORMAL].shade(0.96),
                                       self.bg[gtk.STATE_NORMAL].shade(0.91)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:        self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:        self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED:      self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT:      self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_INSENSITIVE:   self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:        self.fg[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:         gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:         gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT:       gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED:       gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE:    gtk.STATE_INSENSITIVE}
        return states


class Clearlooks(Human):

    def get_properties(self, gtksettings):
        props = Human.get_properties(self, gtksettings)
        props['curvature'] = 3.5
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients

        selected_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.2)

        palette = {gtk.STATE_NORMAL:     (self.bg[gtk.STATE_NORMAL].shade(1.15),
                                          self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:      (self.bg[gtk.STATE_ACTIVE],
                                          self.bg[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED:    (selected_color.shade(1.175),
                                          selected_color),

                  gtk.STATE_PRELIGHT:    (self.bg[gtk.STATE_NORMAL].shade(1.3),
                                          selected_color.shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_light_line_palette(self):
        palette = Human.get_light_line_palette(self)
        palette[gtk.STATE_ACTIVE] = self.bg[gtk.STATE_ACTIVE]
        return palette


class InHuman(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2.5,
            'min-part-width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow-width': 13,
            'scroll-duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override-base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:     (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                          self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:      (self.bg[gtk.STATE_NORMAL].shade(1.00),
                                          self.bg[gtk.STATE_NORMAL].shade(0.75)),

                  gtk.STATE_SELECTED:    (self.bg[gtk.STATE_NORMAL].shade(1.09),
                                          self.bg),

                  gtk.STATE_PRELIGHT:    (self.bg[gtk.STATE_SELECTED].shade(1.35),
                                          self.bg[gtk.STATE_SELECTED].shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:        self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:        self.text[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT:      self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE:   self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:        self.bg[gtk.STATE_ACTIVE].lighten(),
                   gtk.STATE_PRELIGHT:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:         gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:         gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT:       gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED:       gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE:    gtk.STATE_INSENSITIVE}
        return states


class DustSand(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 3,
            'min-part-width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 5,
            'arrow-width': 13,
            'scroll-duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override-base': False
            }
        return props

    def get_grad_palette(self):

        selected_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.4)

        prelight_color = self.bg[gtk.STATE_NORMAL].mix(self.bg[gtk.STATE_SELECTED],
                                                       0.175)

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:    (self.bg[gtk.STATE_NORMAL].shade(1.42),
                                         self.bg[gtk.STATE_NORMAL].shade(1.1)),

                  gtk.STATE_ACTIVE:      (prelight_color,
                                          prelight_color.shade(1.07)),

                  gtk.STATE_SELECTED:    (selected_color.shade(1.35),
                                          selected_color.shade(1.1)),

                  gtk.STATE_PRELIGHT:    (prelight_color.shade(1.74),
                                          prelight_color.shade(1.42)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:      self.text[gtk.STATE_ACTIVE],
                   gtk.STATE_SELECTED:    self.text[gtk.STATE_SELECTED],
                   gtk.STATE_PRELIGHT:    self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_NORMAL].shade(0.575),
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE].shade(0.5),
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT].shade(0.575),
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_SELECTED].shade(0.575),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_NORMAL].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE].shade(0.95),
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT].lighten(),
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:      gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:      gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT:    gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED:    gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class Dust(DustSand):

    def get_grad_palette(self):

        selected_color = color_from_string('#D9C7BD')

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:    (self.bg[gtk.STATE_NORMAL].shade(1.145),
                                         self.bg[gtk.STATE_NORMAL].shade(0.985)),

                  gtk.STATE_ACTIVE:      (self.bg[gtk.STATE_ACTIVE].shade(1.2),
                                          self.bg[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED:    (selected_color.shade(1.2),
                                          selected_color.shade(0.975)),

                  gtk.STATE_PRELIGHT:    (self.bg[gtk.STATE_PRELIGHT].shade(1.35),
                                          self.bg[gtk.STATE_PRELIGHT].shade(1.05)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_dark_line_palette(self):
        palette = DustSand.get_dark_line_palette(self)
        palette[gtk.STATE_SELECTED] = self.bg[gtk.STATE_NORMAL].shade(0.575)
        return palette

    def get_light_line_palette(self):
        palette = DustSand.get_light_line_palette(self)
        palette[gtk.STATE_NORMAL] = self.bg[gtk.STATE_NORMAL].shade(1.1)
        selected_color = color_from_string('#D9C7BD')
        palette[gtk.STATE_SELECTED] = selected_color.shade(1.2)
        return palette


class Ambiance(DustSand):

    def get_properties(self, gtksettings):
        props = DustSand.get_properties(self, gtksettings)
        props['curvature'] = 4.5
        return props

    def get_grad_palette(self):
        focus_color = color_from_string('#FE765E')
        selected_color = self.bg[gtk.STATE_NORMAL].mix(focus_color,
                                                       0.07)
        prelight_color = self.bg[gtk.STATE_NORMAL].mix(focus_color,
                                                       0.33)

        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:    (self.bg[gtk.STATE_NORMAL],
                                         self.bg[gtk.STATE_NORMAL].shade(0.85)),

                  gtk.STATE_ACTIVE:     (self.bg[gtk.STATE_NORMAL].shade(0.94),
                                         self.bg[gtk.STATE_NORMAL].shade(0.65)),

                  gtk.STATE_SELECTED:   (selected_color.shade(1.0),
                                         selected_color.shade(0.85)),
    
                  gtk.STATE_PRELIGHT:   (prelight_color.shade(1.35),
                                         prelight_color.shade(1.1)),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette


class Radiance(Ambiance):

    def get_grad_palette(self):
        palette = Ambiance.get_grad_palette(self)
        palette[gtk.STATE_NORMAL] =  (self.base[gtk.STATE_NORMAL].shade(1.25),
                                      self.bg[gtk.STATE_NORMAL].shade(0.9))
        return palette


class NewWave(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 2,
            'min-part-width': 48,
            'xpad': 8,
            'ypad': 4,
            'xthickness': 1,
            'ythickness': 1,
            'spacing': 4,
            'arrow-width': 13,
            'scroll-duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override-base': True
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients

        active_color = self.bg[gtk.STATE_ACTIVE].mix(color_from_string('#FDCF9D'),
                                                     0.45)

        selected_color = self.bg[gtk.STATE_NORMAL].mix(color_from_string('#FDCF9D'),
                                                       0.2)

        palette = {gtk.STATE_NORMAL:    (self.bg[gtk.STATE_NORMAL].shade(1.1),
                                         self.bg[gtk.STATE_NORMAL].shade(0.95)),

                  gtk.STATE_ACTIVE:     (active_color.shade(1.1),
                                         self.bg[gtk.STATE_ACTIVE].shade(0.95)),

                  gtk.STATE_PRELIGHT:   (color_from_string('#FDCF9D'),
                                         color_from_string('#FCAE87')),

                  gtk.STATE_SELECTED:   (selected_color.shade(1.2),
                                         selected_color),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:        self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:        self.text[gtk.STATE_NORMAL],
                   gtk.STATE_PRELIGHT:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_SELECTED:      self.text[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE:   self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_ACTIVE:        self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_PRELIGHT:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_NORMAL].darken(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE].darken()}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:        self.bg[gtk.STATE_NORMAL].lighten(),
                   gtk.STATE_ACTIVE:        self.bg[gtk.STATE_ACTIVE].shade(0.97),
                   gtk.STATE_PRELIGHT:      color_from_string('#FDCF9D'),
                   gtk.STATE_SELECTED:      self.bg[gtk.STATE_SELECTED].lighten(),
                   gtk.STATE_INSENSITIVE:   self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:         gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:         gtk.STATE_NORMAL,
                  gtk.STATE_PRELIGHT:       gtk.STATE_NORMAL,
                  gtk.STATE_SELECTED:       gtk.STATE_NORMAL,
                  gtk.STATE_INSENSITIVE:    gtk.STATE_INSENSITIVE}
        return states


class Hicolor(Theme):

    def get_properties(self, gtksettings):
        props = {
            'curvature': 0,
            'min-part-width': 48,
            'xpad': 15,
            'ypad': 10,
            'xthickness': 2,
            'ythickness': 2,
            'spacing': 10,
            'arrow-width': 15,
            'scroll-duration': 150,
            'enable-animations': gtksettings.get_property("gtk-enable-animations"),
            'override-base': False
            }
        return props

    def get_grad_palette(self):
        # provide two colours per state for background vertical linear gradients
        palette = {gtk.STATE_NORMAL:     (self.base[gtk.STATE_NORMAL],
                                          self.base[gtk.STATE_NORMAL]),

                  gtk.STATE_ACTIVE:      (self.base[gtk.STATE_ACTIVE],
                                          self.base[gtk.STATE_ACTIVE]),

                  gtk.STATE_SELECTED:    (self.base[gtk.STATE_SELECTED],
                                          self.base[gtk.STATE_SELECTED]),

                  gtk.STATE_PRELIGHT:    (self.base[gtk.STATE_PRELIGHT],
                                          self.base[gtk.STATE_PRELIGHT]),

                  gtk.STATE_INSENSITIVE: (self.bg[gtk.STATE_INSENSITIVE],
                                          self.bg[gtk.STATE_INSENSITIVE])
                  }
        return palette

    def get_text_palette(self):
        palette = {gtk.STATE_NORMAL:      self.text[gtk.STATE_NORMAL],
                   gtk.STATE_ACTIVE:      self.text[gtk.STATE_ACTIVE],
                   gtk.STATE_SELECTED:    self.text[gtk.STATE_SELECTED],
                   gtk.STATE_PRELIGHT:    self.text[gtk.STATE_PRELIGHT],
                   gtk.STATE_INSENSITIVE: self.text[gtk.STATE_INSENSITIVE]}
        return palette

    def get_dark_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE],
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT],
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_light_line_palette(self):
        palette = {gtk.STATE_NORMAL:      self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_ACTIVE:      self.bg[gtk.STATE_ACTIVE],
                   gtk.STATE_PRELIGHT:    self.bg[gtk.STATE_PRELIGHT],
                   gtk.STATE_SELECTED:    self.bg[gtk.STATE_SELECTED],
                   gtk.STATE_INSENSITIVE: self.bg[gtk.STATE_INSENSITIVE]}
        return palette

    def get_text_states(self):
        states = {gtk.STATE_NORMAL:      gtk.STATE_NORMAL,
                  gtk.STATE_ACTIVE:      gtk.STATE_ACTIVE,
                  gtk.STATE_PRELIGHT:    gtk.STATE_PRELIGHT,
                  gtk.STATE_SELECTED:    gtk.STATE_SELECTED,
                  gtk.STATE_INSENSITIVE: gtk.STATE_INSENSITIVE}
        return states


class ThemeRegistry:

    REGISTRY = {"Human": Human,
                "Human-Clearlooks": Clearlooks,
                "Clearlooks": Clearlooks,
                "InHuman": InHuman,
                "HighContrastInverse": Hicolor,
                "HighContrastLargePrintInverse": Hicolor,
                "Dust": Dust,
                "Dust Sand": DustSand,
                "New Wave": NewWave,
                "Ambiance": Ambiance,
                "Ambiance-maverick-beta": Ambiance,
                "Radiance": Radiance}

    def retrieve(self, theme_name):
        # To keep the messages to a minimum
        global THEME_MESSAGE_DISPLAYED
        
        if self.REGISTRY.has_key(theme_name):
            if not THEME_MESSAGE_DISPLAYED:
                logging.debug("Styling hints found for %s..." % theme_name)
                THEME_MESSAGE_DISPLAYED = True
            return self.REGISTRY[theme_name]()

        if not THEME_MESSAGE_DISPLAYED:
            logging.warn("No styling hints for %s were found... using Human hints." % theme_name)
            THEME_MESSAGE_DISPLAYED = True
        from mkit_themes import Clearlooks
        return Clearlooks()


# color coversion functions, these also appear in mkit
def color_from_gdkcolor(gdkcolor):
    return Color(gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float)

def color_from_string(spec):
    gdkcolor = gtk.gdk.color_parse(spec)
    return Color(gdkcolor.red_float, gdkcolor.green_float, gdkcolor.blue_float)
