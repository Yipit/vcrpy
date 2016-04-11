# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import urlparse
import sqlalchemy as sqla
import cPickle
import sys
import re

metadata = sqla.MetaData()
Entries = sqla.Table('entries', metadata,
                     sqla.Column('id', sqla.String(1024), index=True, primary_key=True),
                     sqla.Column('url', sqla.String(1024), index=True, nullable=False),
                     sqla.Column('request', sqla.Binary()),
                     sqla.Column('response',sqla.Binary()))

if len(sys.argv) == 1:
    print "Usage:  python {} \033[90mFIXTURE_FILES\033[0m".format(sys.argv[0])
    quit()

fixtures = sys.argv
fixtures.pop(0)
for fixture in fixtures:
    connection = sqla.create_engine('sqlite:///' + fixture).connect()
    print
    print "\033[94m{}\033[0m".format(fixture)

    for entry in connection.execute("select id, url, request from entries"):
        print "\033[97m {}\033[0m".format(entry['url'])
        parsed_url = urlparse.urlparse(entry['url'])
        if parsed_url.scheme == 'https' and parsed_url.netloc.endswith(':443'):
            new_fields = {}
            parsed_url = parsed_url._replace(netloc=re.sub(':443$', '', parsed_url.netloc))
            new_url = urlparse.urlunparse(parsed_url)
            print "\033[90m   url to \033[0m{}".format(entry['url'], new_url)
            new_fields['url'] = new_url

            request = cPickle.loads(str(entry['request']))
            parsed_url = urlparse.urlparse(request.uri)
            parsed_url = parsed_url._replace(netloc=re.sub(':443$', '', parsed_url.netloc))
            new_url = urlparse.urlunparse(parsed_url)
            request.uri = new_url
            new_fields['request'] = cPickle.dumps(request)

            new_fields['id'] = hash(request.url + ":" + request.method.lower())
            print "\033[90m   hash id from \033[0m{}\033[90m to \033[0m{}".format(entry['id'], new_fields['id'])

            if connection.execute("select count(*) from entries where id='{}'".format(new_fields['id'])).fetchone()[0] == 1:
                connection.execute(sqla.delete(Entries).where(Entries.c.id == entry['id']))
                print "   \033[1m\033[91m[WARNING]\033[0m \033[31mkey conflict, older fixture version deleted!"
            else:
                connection.execute(sqla.update(Entries).where(Entries.c.id == entry['id']).values(new_fields))
                print "\033[92m   fixture updated"
        else:
            print "\033[32m   no change needed\033[0m"
