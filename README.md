Morgan Freeman
==============

A server-side statistics tool for icecast server.

(Like Google Analytics, but worst.)

* collects real data about listeners on single streams
* statistics visualization by html5 web app
* no svg nor pre-rendered images, just canvas2d
* full client-side data manipulation

Installation from source
------------------------

    $ git clone https://github.com/radiocicletta/morganfreeman.git
    $ cd morganfreeman
    $ virtualenv .
    $ pip install -r requirements.txt
    $ wget http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz
    $ gunzip GeoLite2-City.mmdb.gz

Server initialization
---------------------

The server-side collect-and-store engine is a standalone multithread process. A *collector* thread which polls the icecast server and store informations about listeners, and a *http server* thread listening at port 9000 which provides main interface and data.

run the server simply by invoking from shell (inside the virtualenv):

    $ python morganfreeman/frosty.py -h <hostname> -u <username> -w <password> -b <bindport> [-d]

* *hostname* is the icecast server to query (e.g. http://radiocicletta.it:8000 )
* *username* and *password* are credentials required to read the \*xsl pages provided by icecast
* *bindport* is the listen port of the webserver (default 9000)
* *-d* is the daemonize option


Client side usage
-----------------

Simply go to http://localhost:9000 and enjoy.
