# -*- coding: utf-8 -*-
'''Test requests' interaction with vcr'''

import json

import pytest
import vcr

from assertions import assert_cassette_empty, assert_is_json


http = pytest.importorskip("tornado.httpclient")


@pytest.fixture(params=['simple', 'curl', 'default'])
def get_client(request):
    if request.param == 'simple':
        from tornado import simple_httpclient as simple
        return (lambda: simple.SimpleAsyncHTTPClient())
    elif request.param == 'curl':
        curl = pytest.importorskip("tornado.curl_httpclient")
        return (lambda: curl.CurlAsyncHTTPClient())
    else:
        return (lambda: http.AsyncHTTPClient())


def get(client, url, **kwargs):
    raise_error = kwargs.pop('raise_error', True)
    return client.fetch(
        http.HTTPRequest(url, method='GET', **kwargs),
        raise_error=raise_error,
    )


def post(client, url, data=None, **kwargs):
    if data:
        kwargs['body'] = json.dumps(data)
    return client.fetch(http.HTTPRequest(url, method='POST', **kwargs))


@pytest.fixture(params=["https", "http"])
def scheme(request):
    '''Fixture that returns both http and https.'''
    return request.param


@pytest.mark.gen_test
def test_status_code(get_client, scheme, tmpdir):
    '''Ensure that we can read the status code'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))):
        status_code = (yield get(get_client(), url)).code

    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))) as cass:
        assert status_code == (yield get(get_client(), url)).code
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_headers(get_client, scheme, tmpdir):
    '''Ensure that we can read the headers back'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))):
        headers = (yield get(get_client(), url)).headers

    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        assert headers == (yield get(get_client(), url)).headers
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_body(get_client, tmpdir, scheme):
    '''Ensure the responses are all identical enough'''

    url = scheme + '://httpbin.org/bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('body.yaml'))):
        content = (yield get(get_client(), url)).body

    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        assert content == (yield get(get_client(), url)).body
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_auth(get_client, tmpdir, scheme):
    '''Ensure that we can handle basic auth'''
    auth = ('user', 'passwd')
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))):
        one = yield get(
            get_client(), url, auth_username=auth[0], auth_password=auth[1]
        )

    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))) as cass:
        two = yield get(
            get_client(), url, auth_username=auth[0], auth_password=auth[1]
        )
        assert one.body == two.body
        assert one.code == two.code
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_auth_failed(get_client, tmpdir, scheme):
    '''Ensure that we can save failed auth statuses'''
    auth = ('user', 'wrongwrongwrong')
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth-failed.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = yield get(
            get_client(),
            url,
            auth_username=auth[0],
            auth_password=auth[1],
            raise_error=False
        )

    with vcr.use_cassette(str(tmpdir.join('auth-failed.yaml'))) as cass:
        two = yield get(
            get_client(),
            url,
            auth_username=auth[0],
            auth_password=auth[1],
            raise_error=False
        )
        assert one.body == two.body
        assert one.code == two.code == 401
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_post(get_client, tmpdir, scheme):
    '''Ensure that we can post and cache the results'''
    data = {'key1': 'value1', 'key2': 'value2'}
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))):
        req1 = (yield post(get_client(), url, data)).body

    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        req2 = (yield post(get_client(), url, data)).body

    assert req1 == req2
    assert 1 == cass.play_count


@pytest.mark.gen_test
def test_redirects(get_client, tmpdir, scheme):
    '''Ensure that we can handle redirects'''
    url = scheme + '://httpbin.org/redirect-to?url=bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))):
        content = (yield get(get_client(), url)).body

    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        assert content == (yield get(get_client(), url)).body
        assert cass.play_count == 1


@pytest.mark.gen_test
def test_cross_scheme(get_client, tmpdir, scheme):
    '''Ensure that requests between schemes are treated separately'''
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join('cross_scheme.yaml'))) as cass:
        yield get(get_client(), 'https://httpbin.org/')
        yield get(get_client(), 'http://httpbin.org/')
        assert cass.play_count == 0
        assert len(cass) == 2

    # Then repeat the same requests and ensure both were replayed.
    with vcr.use_cassette(str(tmpdir.join('cross_scheme.yaml'))) as cass:
        yield get(get_client(), 'https://httpbin.org/')
        yield get(get_client(), 'http://httpbin.org/')
        assert cass.play_count == 2


@pytest.mark.gen_test
def test_gzip(get_client, tmpdir, scheme):
    '''
    Ensure that httpclient is able to automatically decompress the response
    body
    '''
    url = scheme + '://httpbin.org/gzip'

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))):
        response = yield get(get_client(), url, decompress_response=True)
        assert_is_json(response.body)

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))) as cass:
        response = yield get(get_client(), url, decompress_response=True)
        assert_is_json(response.body)
        assert 1 == cass.play_count


@pytest.mark.gen_test
def test_https_with_cert_validation_disabled(get_client, tmpdir):
    cass_path = str(tmpdir.join('cert_validation_disabled.yaml'))

    with vcr.use_cassette(cass_path):
        yield get(get_client(), 'https://httpbin.org', validate_cert=False)

    with vcr.use_cassette(cass_path) as cass:
        yield get(get_client(), 'https://httpbin.org', validate_cert=False)
        assert 1 == cass.play_count
