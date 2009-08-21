#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *
import glob
import os

setup(name="app-center", version='0.1',
      scripts=["app-center",
               "utils/update-app-center"
               ],
      packages = ['appcenter',
                  'appcenter.view',
                 ],
      data_files=[
                  ('share/app-center/ui/',
                   ["data/ui/AppCenter.ui",
                   ]),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n }
      )


