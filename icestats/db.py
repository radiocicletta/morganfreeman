import sqlite3 as dbapi
import os
import time

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
    useragent text
);""",
"""create index mountid on listener(mount_id);
""")


class DB:

    def __init__(self, patharg):
        dbpath = "%s" % os.path.realpath(patharg)
        prepare = not os.path.exists(dbpath)
        self.db = dbapi.connect(dbpath)
        if prepare:
            for sql in DBSCHEMA:
                self.db.execute(sql)

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

            self.db.execute(
                "insert into listener"
                " (mount_id, ip, listenstart, listenstop, useragent)"
                " values (?, ?, ?, ?, ?)", (
                mid, ip, int((now - duration) * 1000),
                int(now * 1000), useragent))

        else:  # aficionado listener
            self.db.execute(
                "update listener set listenstop = ? where id = ?", (
                int(now * 1000), int(recent[1])))

        self.db.commit()

    def get(self, mount=None, start=0, stop=0):
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
                 'useragent': listener[5]
                 }
            if listener[6] not in result:
                result[listener[6]] = []
            result[listener[6]].append(l)

        return result

    def query(self, **kwargs):
        pass
