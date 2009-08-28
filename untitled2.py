#!/usr/bin/env python
import sys
from subprocess import Popen,PIPE
import sys


folder = sys.argv[1]
text = sys.argv[2] 

p = Popen(["find","-type","f","-name","*svg"], cwd=folder, stdout=PIPE)
files =  p.stdout.read()
filelist = files.split('\n')

for f in filelist:
	c = Popen(["grep",text,""+f+""], cwd=folder, stdout=PIPE)
	c1 =  c.stdout.read()
	if c1 != "":
		print ""+f+":"
		print ""
		print c1
		i = raw_input("")
		while i == 0:
			pass
	

print "Done"
