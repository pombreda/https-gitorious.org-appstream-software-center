#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *
import glob
import os

NAME='mpt-center'

    
setup(name=NAME, version='0.1',
      scripts=[NAME,
               ],
      packages = ['AppCenter'
                 ],
      data_files=[
                  ('share/app-center/ui/',
                   ["data/ui/AppCenter.ui",
                   ]),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n }
      )


