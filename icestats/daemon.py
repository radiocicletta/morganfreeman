__version__ = "0.1"
__author__ = "radiocicletta <radiocicletta@gmail.com>"

import threading
from socketserver import ThreadingTCPServer
from http.server import SimpleHTTPRequestHandler
from .db import DB
import logging
import urllib.request, urllib.error, urllib.parse
from urllib.parse import unquote
import re
import mimetypes
import os
import sys
import json
from io import StringIO

logger = logging.getLogger('icecast.daemon')

ICECAST_V_2_3 = '2.3.'
ICECAST_V_2_4 = '2.4.'
ICECAST_V_KH = '-kh'


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
        logger.info("GET %s", self.path)
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

    def __init__(self, db, host, user, pw, realm='Icecast2 Server', path='.'):
        threading.Thread.__init__(self)

        self.host = host
        self.user = user
        self.pw = pw
        self.realm = realm
        self.db = db
        self.abspath = path

    def run(self):

        logger.debug("launched StatsCollector Instance")
        try:
            result = urllib.request.urlopen(self.host + "/server_version.xsl")
        except Exception as e:
            print(e)
            logger.error("Failed update: %s", e)
            result = None
        resultstr = result.read()
        server_info = dict(
            re.findall(
                '<tr[^>]*>[\r\s]*<td[^>]*>([^\r<>]*?)</td>[\s\r]*'
                '<td[^>]*>([^\r<>]*?)</td>',
                resultstr)
            )
        server_version = re.match("Icecast (.*)", server_info['Version']).groups()[0]

        def timedupdate():
            logger.info("-- MARK --")
            auth_handler = urllib.request.HTTPBasicAuthHandler()
            auth_handler.add_password(
                realm=self.realm,
                uri=self.host + "/admin/",
                user=self.user,
                passwd=self.pw)
            auth_handler_mounts = urllib.request.HTTPBasicAuthHandler()
            auth_handler_mounts.add_password(
                realm=self.realm,
                uri=self.host + "/admin/listmounts.xsl",
                user=self.user,
                passwd=self.pw)
            opener_mounts = urllib.request.build_opener(auth_handler_mounts)
            urllib.request.install_opener(opener_mounts)
            # 1. retrieve all the current mount points
            # 2. for each mount point
            #   gather information about listeners
            #   store in database
            try:
                result = urllib.request.urlopen(self.host + "/admin/listmounts.xsl")
            except Exception as e:
                logger.error("Failed update: %s", e)
                result = None

            if not result:
                return
            db = DB(self.db)

            mountpoints = re.findall(
                "listclients\.xsl\?mount=/([^\"]*)", result.read())
            for mount in mountpoints:
                h_m = urllib.request.HTTPBasicAuthHandler()
                h_m.add_password(
                    realm=self.realm,
                    uri=self.host + "/admin/listclients.xsl?mount=/" + mount,
                    user=self.user,
                    passwd=self.pw)
                o_m = urllib.request.build_opener(h_m)
                urllib.request.install_opener(o_m)
                try:
                    result = urllib.request.urlopen(
                        self.host + "/admin/listclients.xsl?mount=/" + mount)
                except:
                    logger.error("skipping %s", mount)
                    continue

                resultstr = result.read()
                try:
                    # the latest (fourth in vanilla, third in -kh) table
                    # on listclients.xls is the relevant one
                    table = re.findall(
                        "<table[^>]*>([^\r]*?)</table>", resultstr)[-1]
                except:
                    # 2.4.0
                    _table = re.findall(
                        '<table[^>]*class="colortable"[^>]*>([^\r]*?)</table>', resultstr)
                    if not _table:
                        continue
                    table = _table[0]
                listeners = re.findall("<tr[^>]*>([^\r]*?)</tr>", table)

                if ICECAST_V_KH in server_version:
                    rowskip = 0
                else:
                    rowskip = 1
                # in icecast vanilla, first row is the
                # table header. in -kh, the header is enclosed in <thead>
                # without use of <tr>
                logger.debug("registering %d entries", len(listeners) - rowskip)
                for listener in listeners[rowskip:]:
                    fields = re.findall("<td[^>]*>([^\r]*?)</td>", listener)
                    if not ICECAST_V_KH in server_version: # vanilla
                        # fields[0]: IP
                        # fields[1]: Seconds since connection
                        # fields[2]: user-agent
                        # fields[3]: action
                        db.record(mount, fields[0], int(fields[1]), fields[2])
                    else:
                        # fields[0]: IP
                        # fields[1]: Seconds since connection
                        # fields[2]: lag
                        # fields[3]: user-agent
                        # fields[4]: action
                        db.record(mount, fields[0], int(fields[1]), fields[3])

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
                 realm,
                 bindport=9000,
                 uas=[]):

        self.abspath = os.path.abspath(".")
        self.host = host
        self.username = username
        self.password = password
        self.realm = realm
        self.bindport = bindport
        self.useragents = [re.compile(s) for s in uas]

    def run(self):

        logger.debug("Daemon initialized")

        mimetypes.init()

        stats = StatsCollector(
            "%s/stats.sqlite" % self.abspath,
            self.host,
            self.username,
            self.password,
            self.realm,
            self.abspath)
        logger.debug("StatsCollector initialized")
        stats.start()

        http = StatsThreadingTCPServer(
            ('0.0.0.0', self.bindport),
            StatsHTTPRequestHandler,
            self.abspath,
            self.useragents)
        logger.debug("HTTP server initialized")
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
