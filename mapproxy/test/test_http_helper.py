# This file is part of the MapProxy project.
# Copyright (C) 2013 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests

from mapproxy.test.http import (
    MockServ, RequestsMismatchError, mock_httpd,
    basic_auth_value, query_eq,
)


class TestMockServ(object):
    def test_no_requests(self):
        serv = MockServ()
        with serv:
            pass

    def test_expects_get_no_body(self):
        serv = MockServ()
        serv.expects('/test')
        with serv:
            resp = requests.get('http://localhost:%d/test' % serv.port)
            assert resp.status_code == 200
            assert resp.content == b''

    def test_expects_w_header(self):
        serv = MockServ()
        serv.expects('/test', headers={'Accept': 'Coffee'})
        with serv:
            resp = requests.get('http://localhost:%d/test' % serv.port, headers={'Accept': 'Coffee'})
            assert resp.ok

    def test_expects_w_header_but_missing(self):
        serv = MockServ()
        serv.expects('/test', headers={'Accept': 'Coffee'})
        try:
            with serv:
                requests.get('http://localhost:%d/test' % serv.port)
        except RequestsMismatchError as ex:
            assert ex.assertions[0].expected == 'Accept: Coffee'

    def test_expects_post(self):
        # TODO POST handling in MockServ is hacky.
        # data just  gets appended to URL
        serv = MockServ()
        serv.expects('/test?foo', method='POST')
        with serv:
            requests.post('http://localhost:%d/test' % serv.port, data=b'foo')

    def test_expects_post_but_get(self):
        serv = MockServ()
        serv.expects('/test', method='POST')
        try:
            with serv:
                requests.get('http://localhost:%d/test' % serv.port)
        except RequestsMismatchError as ex:
            assert ex.assertions[0].expected == 'POST'
            assert ex.assertions[0].actual == 'GET'
        else:
            raise AssertionError('AssertionError expected')

    def test_returns(self):
        serv = MockServ()
        serv.expects('/test')
        serv.returns(body=b'hello')

        with serv:
            resp = requests.get('http://localhost:%d/test' % serv.port)
            assert 'Content-type' not in resp.headers
            assert resp.content == b'hello'

    def test_returns_headers(self):
        serv = MockServ()
        serv.expects('/test')
        serv.returns(body=b'hello', headers={'content-type': 'text/plain'})

        with serv:
            resp = requests.get('http://localhost:%d/test' % serv.port)
            assert resp.headers['Content-type'] == 'text/plain'
            assert resp.content == b'hello'

    def test_returns_status(self):
        serv = MockServ()
        serv.expects('/test')
        serv.returns(body=b'hello', status_code=418)

        with serv:
            resp = requests.get('http://localhost:%d/test' % serv.port)
            assert resp.status_code == 418
            assert resp.content == b'hello'


    def test_multiple_requests(self):
        serv = MockServ()
        serv.expects('/test1').returns(body=b'hello1')
        serv.expects('/test2').returns(body=b'hello2')

        with serv:
            resp = requests.get('http://localhost:%d/test1' % serv.port)
            assert resp.content == b'hello1'
            resp = requests.get('http://localhost:%d/test2' % serv.port)
            assert resp.content == b'hello2'


    def test_too_many_requests(self):
        serv = MockServ()
        serv.expects('/test1').returns(body=b'hello1')

        with serv:
            resp = requests.get('http://localhost:%d/test1' % serv.port)
            assert resp.content == b'hello1'
            try:
                requests.get('http://localhost:%d/test2' % serv.port)
            except requests.exceptions.RequestException:
                pass
            else:
                raise AssertionError('RequestException expected')

    def test_missing_requests(self):
        serv = MockServ()
        serv.expects('/test1').returns(body=b'hello1')
        serv.expects('/test2').returns(body=b'hello2')

        try:
            with serv:
                resp = requests.get('http://localhost:%d/test1' % serv.port)
                assert resp.content == b'hello1'
        except RequestsMismatchError as ex:
            assert 'requests mismatch:\n -  missing requests' in str(ex)
        else:
            raise AssertionError('AssertionError expected')

    def test_reset_unordered(self):
        serv = MockServ(unordered=True)
        serv.expects('/test1').returns(body=b'hello1')
        serv.expects('/test2').returns(body=b'hello2')

        with serv:
            resp = requests.get('http://localhost:%d/test1' % serv.port)
            assert resp.content == b'hello1'
            resp = requests.get('http://localhost:%d/test2' % serv.port)
            assert resp.content == b'hello2'

        serv.reset()
        with serv:
            resp = requests.get('http://localhost:%d/test2' % serv.port)
            assert resp.content == b'hello2'
            resp = requests.get('http://localhost:%d/test1' % serv.port)
            assert resp.content == b'hello1'

    def test_unexpected(self):
        serv = MockServ(unordered=True)
        serv.expects('/test1').returns(body=b'hello1')
        serv.expects('/test2').returns(body=b'hello2')

        try:
            with serv:
                resp = requests.get('http://localhost:%d/test1' % serv.port)
                assert resp.content == b'hello1'
                try:
                    requests.get('http://localhost:%d/test3' % serv.port)
                except requests.exceptions.RequestException:
                    pass
                else:
                    raise AssertionError('RequestException expected')
                resp = requests.get('http://localhost:%d/test2' % serv.port)
                assert resp.content == b'hello2'
        except RequestsMismatchError as ex:
            assert 'unexpected request' in ex.assertions[0]
        else:
            raise AssertionError('AssertionError expected')


class TestMockHttpd(object):
    def test_no_requests(self):
        with mock_httpd(('localhost', 42423), []):
            pass

    def test_headers_status_body(self):
        with mock_httpd(('localhost', 42423), [
            ({'path':'/test', 'headers': {'Accept': 'Coffee'}},
             {'body': b'ok', 'status': 418})]):
            resp = requests.get('http://localhost:42423/test', headers={'Accept': 'Coffee'})
            assert resp.status_code == 418

    def test_auth(self):
        with mock_httpd(('localhost', 42423), [
            ({'path':'/test', 'headers': {'Accept': 'Coffee'}, 'require_basic_auth': True},
             {'body': b'ok', 'status': 418})]):
                resp = requests.get('http://localhost:42423/test')
                assert resp.status_code == 401
                assert resp.content == b'no access'

                resp = requests.get('http://localhost:42423/test', headers={
                    'Authorization': basic_auth_value('foo', 'bar'), 'Accept': 'Coffee'}
                )
                assert resp.content == b'ok'


def test_query_eq():
    assert query_eq('?baz=42&foo=bar', '?foo=bar&baz=42')
    assert query_eq('?baz=42.00&foo=bar', '?foo=bar&baz=42.0')
    assert query_eq('?baz=42.000000001&foo=bar', '?foo=bar&baz=42.0')
    assert not query_eq('?baz=42.00000001&foo=bar', '?foo=bar&baz=42.0')

    assert query_eq('?baz=42.000000001,23.99999999999&foo=bar', '?foo=bar&baz=42.0,24.0')
    assert not query_eq('?baz=42.00000001&foo=bar', '?foo=bar&baz=42.0')
