# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from six import PY2, PY3
import six

from . import cassette
from .matchers import requests_match
from .errors import UnhandledHTTPRequestError
import sqlalchemy as sqla
if PY2:
    import cPickle
if PY3:
    import _pickle as cPickle
import base64
import copy

metadata = sqla.MetaData()
Entries = sqla.Table('entries', metadata,
                     sqla.Column('id', sqla.String(1024), index=True, primary_key=True),
                     sqla.Column('url', sqla.String(1024), index=True, nullable=False),
                     sqla.Column('request', sqla.Binary()),
                     sqla.Column('response',sqla.Binary()))

def request_id(req):
    d = req._to_dict()
    return req.url + ":" + req.method.lower()

def response_from_db(txt):
    d = cPickle.loads(six.binary_type(txt))
    d['body']['string'] = base64.b64decode(d['body']['string'])
    return d

def response_to_db(response):
    rp = copy.deepcopy(response)
    rp['body']['string'] = base64.b64encode(rp['body']['string'])
    return rp

class SQLiteCassette(cassette.Cassette):
    def __init__(self, *args, **kwargs):
        super(SQLiteCassette, self).__init__(*args, **kwargs)
        self._con = None
        self._engine = None
        self.rewound = True

    def play_response(self, request):
        resp = self._find_response(request)
        if resp is not None:
            return resp
        raise UnhandledHTTPRequestError(
            "The cassette (%r) doesn't contain the request (%r) asked for"
            % (self._path, request))

    def _find_response(self, request):
        """
        Patch for upgrading from Python 2 to Python 3.

        If the `id` column is still a hash, update it to a non-hash (result of request_id). If it's updated already, let it pass.
        """

        if PY3:
            raise Exception('Must be run with Python 2! Downgrade to Python 2 & run the migration there.')

        response_from_old_id = self._find_old_response_and_update(request)
        if response_from_old_id:
            return response_from_old_id

        response_from_new_id = self._con.execute(sqla.select([Entries.c.response]).where(Entries.c.id==request_id(request))).fetchone()
        if response_from_new_id:
            return response_from_db(response_from_new_id[0])

    def _find_old_response_and_update(self, request):
        resp_row_old = self._con.execute(sqla.select([Entries.c.response]).where(Entries.c.id==hash(request_id(request)))).fetchone()
        if resp_row_old:
            update_stmt = sqla.update(Entries).where(Entries.c.id==hash(request_id(request))).values(id=request_id(request))
            print('\n')
            to_update = raw_input('Update id from {} to {}? y/n '.format(hash(request_id(request)), request_id(request)))
            if to_update == 'y':
                self._con.execute(update_stmt)
                print('Updated id from {} to {}!'.format(hash(request_id(request)), request_id(request)))
            return response_from_db(resp_row_old[0])

    def append(self, request, response):
        
        # Handle this explicitly to support ignoring requests to internal services,
        # since we're overwriting cassette.Cassette's `append` which does this.
        request = self._before_record_request(request)
        if not request:
            return
        rp = response_to_db(response)
        q = Entries.insert({'id': request_id(request), 'url': request.url,
                            'request': cPickle.dumps(request),
                            'response': cPickle.dumps(rp)})
        self._con.execute(q)

    def _save(self, force=False):
        pass

    def __contains__(self, request):
        res = self._find_response(request)
        return res is not None

    def __len__(self):
        raise Exception('Not implemented')

    def _load(self):
        self._engine = sqla.create_engine('sqlite:///' + self._path)
        metadata.create_all(self._engine)
        self._con = self._engine.connect()

    @classmethod
    def use(cls, path=None, *args, **kwargs):
        return cassette.CassetteContextDecorator.from_args(cls, path=path, *args, **kwargs)
