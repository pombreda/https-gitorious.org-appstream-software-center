#!/usr/bin/python

import time
from aptdaemon.client import AptClient

c = AptClient()
for i in range(40):
    t = c.commit_packages(["3dchess"], [], [], [], [], exit_handler=lambda x, y: True)
    t.run(block=False)
    t = c.commit_packages([], [], ["3dchess"], [], [], exit_handler=lambda x, y: True)
    t.run(block=False)

    time.sleep(3)

