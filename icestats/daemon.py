__version__ = "0.1"
__author__ = "radiocicletta <radiocicletta@gmail.com>"

import threading
from SocketServer import ThreadingTCPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler
from db import DB
import logging
import urllib2
from urllib import unquote
import re
import mimetypes
import os
import sys
import json
from StringIO import StringIO

logging.basicConfig(filename='./log.log', level=logging.DEBUG)
logger = logging.getLogger('icecast.daemon')


class StatsThreadingTCPServer(ThreadingTCPServer):

    """ threaded tcp server """
    allow_reuse_address = True

    def __init__(self, host, handler, path='.', useragents=[]):

        ThreadingTCPServer.__init__(self, host, handler)
        self.abspath = path
        self.useragents = useragents


class StatsHTTPRequestHandler(SimpleHTTPRequestHandler):

    """ request handler for web requests
        actions:

        /
        /index - html startpoint
        /mounts - list mountpoints
        /mount/<name>|*[/from[/to]]
             retrieve data for mountpoint <name> (* for all) in a range
    """

    def do_GET(self):
        request = re.findall("([^/]+)", unquote(self.path))

        if not request or request[0] == "index":

            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()

            index = open("%s/data/index.html" % self.server.abspath, "r")
            self.copyfile(index, self.wfile)
            index.close()

        elif request[0] == "data":

            try:
                path = "%s/%s" % (self.server.abspath, re.search(
                    "([^?#]+).*", unquote(self.path)).groups()[0])

                if not os.path.exists(os.path.realpath(path)):
                    self.send_response(404)

                else:
                    mime = mimetypes.types_map[re.search(
                        "(\.\w+)$", path, re.I).groups()[0]]
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.end_headers()
                    resource = open(path, "r")
                    self.copyfile(resource, self.wfile)
                    resource.close()

            except:
                self.send_response(500)
                self.end_headers()

        elif request[0] == "mounts":
            try:
                data = StringIO()
                db = DB("%s/stats.sqlite" % self.server.abspath)

                data.write(json.dumps(db.mounts()))
                data.seek(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.copyfile(data, self.wfile)
            except:
                self.send_response(500)
                self.end_headers()

        elif request[0] == "mount":
            try:
                data = StringIO()
                db = DB("%s/stats.sqlite" % self.server.abspath)

                data.write(
                    json.dumps(
                        db.get(
                            request[1],
                            (len(request) > 2 and int(request[2]) or 0),
                            (len(request) > 3 and int(request[3]) or 0),
                            self.server.useragents
                        )
                    )
                )
                data.seek(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.copyfile(data, self.wfile)
            except Exception as e:
                logger.error(e)
                self.end_headers()
                self.send_response(500)

    def do_HEAD(self):
        pass


class StatsCollector(threading.Thread):

    daemon = True

    def __init__(self, db, host, user, pw, path='.'):
        threading.Thread.__init__(self)

        self.host = host
        self.user = user
        self.pw = pw
        self.db = db
        self.abspath = path

    def run(self):

        def timedupdate():
            logger.info("-- MARK --")
            auth_handler = urllib2.HTTPBasicAuthHandler()
            auth_handler.add_password(
                realm="Icecast2 Server",
                uri=self.host + "/admin/",
                user=self.user,
                passwd=self.pw)
            opener = urllib2.build_opener(auth_handler)
            urllib2.install_opener(opener)
            # 1. retrieve all the current mount points
            # 2. for each mount point
            #   gather information about listeners
            #   store in database
            try:
                result = urllib2.urlopen(self.host + "/admin/listmounts.xsl")
            except Exception as e:
                logger.error("Failed update: %s", e)
                result = None

            if not result:
                return
            db = DB(self.db)

            mountpoints = re.findall(
                "listclients\.xsl\?mount=/([^\"]*)", result.read())
            for mount in mountpoints:
                try:
                    result = urllib2.urlopen(
                        self.host + "/admin/listclients.xsl?mount=/" + mount)
                except:
                    logger.error("skipping %s", mount)
                    continue

                resultstr = result.read()
                try:
                    # the fourth table on listclients.xls is the relevant one
                    table = re.findall(
                        "<table[^>]*>([^\r]*?)</table>", resultstr)[3]
                except:
                    # 2.4.0
                    _table = re.findall(
                        '<table[^>]*class="colortable"[^>]*>([^\r]*?)</table>', resultstr)
                    if not _table:
                        continue
                    table = _table[0]
                listeners = re.findall("<tr[^>]*>([^\r]*?)</tr>", table)

                # the first row is the table header
                for listener in listeners[1:]:
                    fields = re.findall("<td[^>]*>([^\r]*?)</td>", listener)
                    # fields[0]: IP
                    # fields[1]: Seconds since connection
                    # fields[2]: user-agent
                    # fields[3]: useless kick link
                    db.record(mount, fields[0], int(fields[1]), fields[2])

        timedupdate()
        while True:
            update = threading.Timer(30.0, timedupdate)
            update.start()
            update.join()


class Daemon:

    def __init__(self,
                 path,
                 host,
                 username,
                 password,
                 bindport=9000,
                 uas=[]):

        self.abspath = os.path.abspath(".")
        self.host = host
        self.username = username
        self.password = password
        self.bindport = bindport
        self.useragents = [re.compile(s) for s in uas]

    def run(self):

        mimetypes.init()

        stats = StatsCollector(
            "%s/stats.sqlite" % self.abspath,
            self.host,
            self.username,
            self.password,
            self.abspath)
        stats.start()

        http = StatsThreadingTCPServer(
            ('0.0.0.0', self.bindport),
            StatsHTTPRequestHandler,
            self.abspath,
            self.useragents)
        http.serve_forever()
        stats.join()

    def daemonize(self,
                  stdin='/dev/null',
                  stdout='/dev/null',
                  stderr='/dev/null'):

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)   # Exit first parent.
        except OSError as e:
            sys.stderr.write("fork #1 failed: (%d) %s\n" % (
                e.errno, e.strerror))
            sys.exit(1)

        os.chdir("/")
        os.umask(0)
        os.setsid()

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)   # Exit second parent.
        except OSError as e:
            sys.stderr.write("fork #2 failed: (%d) %s\n" % (
                e.errno, e.strerror))
            sys.exit(1)

        # Redirect standard file descriptors.
        si = open(stdin, 'r')
        so = open(stdout, 'a+')
        se = open(stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
