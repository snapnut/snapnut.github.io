import sys

if len(sys.argv) != 2:
    print("pass the DIST folder with SOURCE copied to it")
    exit(-1)

# distfs is modify in place, and has source copied already
distfs = sys.argv[1]

