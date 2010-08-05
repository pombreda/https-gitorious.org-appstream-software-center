#!/usr/bin/env python

from distutils.core import setup
from DistUtilsExtra.command import *

import re
import glob
import os
from subprocess import Popen, PIPE, call
import sys

# update version.py
line = open("debian/changelog").readline()
m = re.match("^[\w-]+ \(([\w\.~]+)\) ([\w-]+);", line)
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

# update po4a
if sys.argv[1] == "build":
    call(["po4a", "po/help/po4a.conf"])

# real setup
setup(name="software-center", version=VERSION,
      scripts=["software-center",
               "utils/update-software-center",
               "utils/update-software-center-agent",
               ],
      packages = ['softwarecenter',
                  'softwarecenter.apt',
                  'softwarecenter.backend',
                  'softwarecenter.db',
                  'softwarecenter.distro',
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
                  ('share/software-center/icons/',
                   glob.glob("data/emblems/*.png")),
                  ('share/apt-xapian-index/plugins',
                   glob.glob("apt-xapian-index-plugin/*.py")),
                  ],
      cmdclass = { "build" : build_extra.build_extra,
                   "build_i18n" :  build_i18n.build_i18n,
                   "build_help" : build_help.build_help,
                   "build_icons" : build_icons.build_icons}
      )


