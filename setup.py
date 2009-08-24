#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *
import glob
import os

setup(name="software-store", version='0.1',
      scripts=["software-store",
               "utils/update-software-store"
               ],
      packages = ['appcenter',
                  'appcenter.view',
                 ],
      data_files=[
                  ('share/software-store/ui/',
                   ["data/ui/SoftwareStore.ui",
                   ]),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n }
      )


