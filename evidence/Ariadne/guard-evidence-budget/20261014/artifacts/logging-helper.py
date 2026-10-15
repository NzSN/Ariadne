#!/usr/bin/python3
"""Transparent stdout tee; diagnostic identity is deliberately different."""
import os,sys,subprocess
with open(os.environ['DIAGNOSTIC_LIFT_LOG'],'wb',buffering=0) as log:
 child=subprocess.Popen([os.environ['DIAGNOSTIC_REAL_HELPER'],*sys.argv[1:]],stdin=sys.stdin.buffer,stdout=subprocess.PIPE,stderr=sys.stderr.buffer)
 for line in child.stdout:
  log.write(line)
  sys.stdout.buffer.write(line)
  sys.stdout.buffer.flush()
 sys.exit(child.wait())
