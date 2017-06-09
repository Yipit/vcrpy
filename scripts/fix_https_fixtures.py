# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from six import PY2, PY3

import base64
import urlparse
import sqlalchemy as sqla
if PY2:
    import cPickle
if PY3:
    import _pickle as cPickle
import sys
import re

def to_2x_headers(headers):
        h = {}
        for e in headers:
            key = e.split(':')[0]
            val = ':'.join(e.split(':')[1:])
            if key not in h:
                h[key] = [val[0:-2]]
            else:
                h[key].append(val[0:-2])
        return h


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

    for entry in connection.execute("select id, url, request, response from entries").fetchall():
        print "\033[97m {}\033[0m".format(entry['url'])
        change_needed = False
        parsed_url = urlparse.urlparse(entry['url'])
        request = cPickle.loads(str(entry['request']))

        if parsed_url.scheme == 'https' and parsed_url.netloc.endswith(':443'):
            new_fields = {}
            parsed_url = parsed_url._replace(netloc=re.sub(':443$', '', parsed_url.netloc))
            new_url = urlparse.urlunparse(parsed_url)
            print "\033[90m   url to \033[0m{}".format(entry['url'], new_url)
            new_fields['url'] = new_url

            parsed_url = urlparse.urlparse(request.uri)
            parsed_url = parsed_url._replace(netloc=re.sub(':443$', '', parsed_url.netloc))
            new_url = urlparse.urlunparse(parsed_url)
            request.uri = new_url
            new_request = cPickle.dumps(request)
            new_fields['request'] = new_request

            change_needed = True

        elif str(hash(entry['url'] + ":" + request.method.lower())) != entry['id']:
            request.uri = entry['url']
            new_request = cPickle.dumps(request)

            response = cPickle.loads(str(entry['response']))
            if  'Content-Encoding: gzip\r\n' in response['headers']:
                import zlib
                response['body']['string'] = base64.b64decode(response['body']['string'])
                response['body']['string'] = zlib.decompressobj(16+zlib.MAX_WBITS).decompress(response['body']['string'])
                response['body']['string'] = base64.b64encode(response['body']['string'])
                response['headers'].remove(u'Content-Encoding: gzip\r\n')
            response['headers'] = to_2x_headers(response['headers'])
            new_response = cPickle.dumps(response)

            new_fields = {}
            new_fields['url'] = entry['url']
            new_fields['request'] = new_request
            new_fields['response'] = new_response
            change_needed = True

        if change_needed:
            new_fields['id'] = str(hash(request.url + ":" + request.method.lower()))
            print "\033[90m   hash id from \033[0m{}\033[90m to \033[0m{}".format(entry['id'], new_fields['id'])

            if connection.execute("select count(*) from entries where id='{}'".format(new_fields['id'])).fetchone()[0] >= 1:
                connection.execute(sqla.delete(Entries).where(Entries.c.id == entry['id']))
                print "   \033[1m\033[91m[WARNING]\033[0m \033[31mkey conflict, older fixture version deleted!"
            else:
                connection.execute(sqla.update(Entries).where(Entries.c.id == entry['id']).values(new_fields))
                print "\033[92m   fixture updated"
        else:
            print "   \033[90m{} \033[32mno change needed\033[0m".format(entry['id'])
