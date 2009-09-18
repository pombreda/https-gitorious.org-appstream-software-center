#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

import re
import glob
import os
from subprocess import Popen, PIPE
import sys

# update version.py
line = open("debian/changelog").readline()
m = re.match("^[\w-]+ \(([\w\.]+)\) (\w+);", line)
VERSION = m.group(1)
CODENAME = m.group(2)
DISTRO = Popen(["lsb_release", "-s", "-i"], stdout=PIPE).communicate()[0].strip()
RELEASE = Popen(["lsb_release", "-s", "-r"], stdout=PIPE).communicate()[0].strip()
open("softwarestore/version.py","w").write("""
VERSION='%s'
CODENAME='%s'
DISTRO='%s'
RELEASE='%s'
""" % (VERSION, CODENAME, DISTRO, RELEASE))


setup(name="software-store", version=VERSION,
      scripts=["software-store",
               "utils/update-software-store",
               ],
      packages = ['softwarestore',
                  'softwarestore.apt',
                  'softwarestore.db',
                  'softwarestore.view',
                  'softwarestore.view.widgets',
                 ],
      data_files=[
                  ('share/software-store/ui/',
                   glob.glob("data/ui/*.ui")),
                  ('share/software-store/templates/',
                   glob.glob("data/templates/*.html")),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" : build_help.build_help,
                   "build_icons" : build_icons.build_icons}
      )


