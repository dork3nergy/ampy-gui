"""
Prints all the files in a certain directory, or root if no directory is specified.
"""

import sys, os

root = ""
if len(sys.argv) == 2:
	root = sys.argv[1]
	print("ROOT: {}".format(root))

for file in os.listdir(root):
	# NOTE: os.path does not exist on micropython, hence this weird implementation
	child = "{}/{}".format(root, file)
	st = os.stat(child)
	if not st[0] & 0x4000:  # stat.File
		print(file)
