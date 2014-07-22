import sqlite3 as dbapi
import os
import time
import maxminddb
import sys

DBSCHEMA = ("""
PRAGMA foreign_keys = ON;
""",
"""create table if not exists mount (
    id integer primary key asc autoincrement,
    name text not null
);""",
"""create table if not exists listener(
    id integer primary key asc autoincrement,
    mount_id references mount(id),
    ip text not null,
    listenstart integer,
    listenstop integer,
    useragent text,
    iso_code text,
    country text
);""",
"""create index mountid on listener(mount_id);
""")
MIGRATION_1 = (
    """alter table listener add iso_code text;""",
    """alter table listener add country text;""",
    """pragma user_version = 1;"""
)


class DB:

    def __init__(self, patharg, ip=[], ua=[]):
        dbpath = "%s" % os.path.realpath(patharg)
        prepare = not os.path.exists(dbpath)
        self.db = dbapi.connect(dbpath)
        self.ip = set(ip)
        self.ua = set(ua)
        self.geo = maxminddb.Reader(sys.path[0] + '/GeoLite2-City.mmdb')
        if prepare:
            for sql in DBSCHEMA:
                self.db.execute(sql)
        cur = self.db.execute("pragma user_version")

        # migration
        if cur.fetchone()[0] < 1:
            for sql in MIGRATION_1:
                self.db.execute(sql)
            cur = self.db.execute("select distinct ip from listener")
            while True:
                res = cur.fetchmany(1000)
                if not res:
                    break
                for ip in res:
                    iso, country = self.geoip(ip[0])
                    self.db.execute(
                        "update listener set iso_code = ? , country = ?"
                        "where ip = ?",
                        (iso, country, ip[0])
                    )
            self.db.commit()

    def mounts(self):
        """ retrieve mountpoint lists """

        cur = self.db.execute("select * from mount")
        m = cur.fetchall()
        mounts = {}
        for mount in m:
            mounts[mount[0]] = mount[1]

        return mounts

    def insertmount(self, mount):
        """insert a new mountpoint
           returns the new id"""

        self.db.execute(
            "insert or ignore into mount (name) values (?)", (mount,))
        self.db.commit()

        cur = self.db.execute("select id from mount where name = ? ", (mount,))
        return cur.fetchone()[0]

    def getmount(self, mount):
        """retrieve a mountpoint id or None"""

        cur = self.db.execute("select id from mount where name = ? ", (mount,))
        mid = cur.fetchone()

        if mid:
            return mid[0]
        else:
            return None

    def record(self, stream, ip, duration, useragent):
        """ insert or update informations about listeners """

        ceiltime = duration + (60 - duration % 60)
        now = time.time()
        roundedstart = int(now) - ceiltime

        cur = self.db.execute(
            "select m.id, l.id "
            "from listener l left join mount m on (l.mount_id = m.id)"
            " where ip = ? and listenstop >= ? and m.name = ? limit 1", (
                ip, roundedstart * 1000, stream))
        recent = cur.fetchone()

        if not recent:  # a new listener appears!
            mid = self.getmount(stream)
            if not mid:
                mid = self.insertmount(stream)

            iso, country = self.geoip(ip)

            self.db.execute(
                "insert into listener"
                " (mount_id, ip, listenstart, listenstop,"
                " useragent, iso_code, country)"
                " values (?, ?, ?, ?, ?, ?, ?)", (
                    mid, ip, int((now - duration) * 1000),
                    int(now * 1000), useragent, iso, country))

        else:  # aficionado listener
            self.db.execute(
                "update listener set listenstop = ? where id = ?", (
                    int(now * 1000), int(recent[1])))

        self.db.commit()

    def get(self, mount=None, start=0, stop=0, uas=[]):
        """ retrieve informations about listeners in one
            or many streams in a range of time
            mount == '*' is a shortcut for all mounts"""

        query = "select l.*, m.name from listener l" \
                " left join mount m on (l.mount_id = m.id)"
        queryconds = []
        queryparms = ()
        if mount != "*":
            queryconds.append("m.name = ?")
            queryparms = queryparms + (mount, )
        if start > 0:
            queryconds.append("l.listenstart >= ?")
            queryparms = queryparms + (start, )
        if stop > 0:
            queryconds.append("l.listenstop <= ?")
            queryparms = queryparms + (stop, )

        if queryconds:
            query = "%s where %s " % (query, " and ".join(queryconds))
            cur = self.db.execute(query, queryparms)
        else:
            cur = self.db.execute(query)

        result = {}
        for listener in cur:
            l = {'id': listener[0],
                 'ip': listener[2],
                 'start': listener[3],
                 'stop': listener[4],
                 'useragent': listener[5],
                 'iso': listener[6],
                 'country': listener[7],
                 'type': self.__ua_type(
                     listener[5], uas) and 'bot' or 'listener'
                 }
            result.setdefault(listener[8], [])
            result[listener[8]].append(l)

        return result

    def geoip(self, ip):

        geo = self.geo.get(ip)
        try:
            country = geo['country']['names']['en']
        except:
            country = ''
        try:
            iso = geo['country']['iso_code']
        except:
            iso = ''
        return iso, country

    def __ua_type(self, agent, agentlist):
        for exp in agentlist:
            if exp.search(agent):
                return True
        return False

    def query(self, **kwargs):
        pass
