#!/usr/bin/env python3.6
import sys
import os

from configparser import ConfigParser

c = ConfigParser()
c.read(sys.argv[1])

output = {}

for s in c.sections():
    for k,v in c[s].items():
        print("export {}={}".format(k,v))
