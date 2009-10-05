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
open("softwarecenter/version.py","w").write("""
VERSION='%s'
CODENAME='%s'
DISTRO='%s'
RELEASE='%s'
""" % (VERSION, CODENAME, DISTRO, RELEASE))


setup(name="software-center", version=VERSION,
      scripts=["software-center",
               "utils/update-software-center",
               ],
      packages = ['softwarecenter',
                  'softwarecenter.apt',
                  'softwarecenter.db',
                  'softwarecenter.view',
                  'softwarecenter.view.widgets',
                 ],
      data_files=[
                  ('share/software-center/ui/',
                   glob.glob("data/ui/*.ui")),
                  ('share/software-center/templates/',
                   glob.glob("data/templates/*.html")),
                  ('../etc/dbus-1/system.d/',
                   ["data/com.ubuntu.SoftwareCenter.conf"]),
                  ('share/software-center/images/',
                   glob.glob("data/images/*.png")),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" : build_help.build_help,
                   "build_icons" : build_icons.build_icons}
      )


