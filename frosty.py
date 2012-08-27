#!/bin/env python2.6

from getopt import getopt
import sys
from icestats import daemon

if __name__ == '__main__':

    args, opts = getopt(sys.argv[1:], "h:b:u:w:d", ["help","host=", "bind=", "username=", "password=", "daemonize"])

    daemonize = False

    for k, v in args:
        if k == '--help':
            print "ZOMG"
            sys.exit(1)
        elif k in ('-d', '--daemonize'):
            daemonize = True
        elif k in ('-h', '--host'):
            if not v:
                raise Exception()
            host = v
        elif k in ('-b', '--bind'):
            if not v:
                raise Exception()
            port = int(v)
        elif k in ('-u', '--username'):
            if not v:
                raise Exception()
            username = v
        elif k in ('-w', '--password'):
            if not v:
                raise Exception()
            password = v

    process = daemon.Daemon('.', host, username, password, port)
    if daemonize:
        process.daemonize()

    process.run()
