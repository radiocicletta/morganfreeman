#!/bin/env python2.7

from getopt import getopt
import sys
from icestats import daemon
from settings import *
import logging
from datetime import datetime

logging.captureWarnings(True)

if __name__ == '__main__':

    args, opts = getopt(
        sys.argv[1:],
        "h:b:u:w:r:d",
        ["help",
         "host=",
         "bind=",
         "username=",
         "password=",
         "realm=",
         "daemonize"])

    daemonize = False

    realm = None

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
        elif k in ('-r', '--realm'):
            realm = v

    formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
    )
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
        filename='logs/access_{}.log'.format(
            datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        )
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)

    logging.getLogger('').addHandler(console)

    logger = logging.getLogger(__name__)
    logger.debug("Process starting")

    try:
        process = daemon.Daemon('.', host, username, password, realm, port, useragent_bots)
        logger.debug("Process started")
    except:
        process = daemon.Daemon('.', host, username, password, realm, port)
        logger.debug("Process started")
    if daemonize:
        process.daemonize()
        logger.debug("Process daemonized")

    process.run()
