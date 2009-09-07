#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *
import glob
import os

setup(name="software-store", version='0.2',
      scripts=["software-store",
               "utils/update-software-store",
               ],
      packages = ['softwarestore',
                  'softwarestore.apt',
                  'softwarestore.view',
                 ],
      data_files=[
                  ('share/software-store/ui/',
                   ["data/ui/SoftwareStore.ui",
                   ]),
                  ('share/software-store/templates/',
                   glob.glob("data/templates/*.html")),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" : build_help.build_help,
                   "build_icons" : build_icons.build_icons}
      )


