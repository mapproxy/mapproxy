# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

from io import BytesIO

from mapproxy.test.helper import Mocker
from mapproxy.test.mocker import ANY
from mapproxy.response import Response
from mapproxy.compat import string_type

class TestResponse(Mocker):
    def test_str_response(self):
        resp = Response('string content')
        assert isinstance(resp.response, string_type)
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert next(result) == b'string content'

    def test_itr_response(self):
        resp = Response(iter(['string content', 'as iterable']))
        assert hasattr(resp.response, 'next') or hasattr(resp.response, '__next__')
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert next(result) == 'string content'
        assert next(result) == 'as iterable'

    def test_file_response(self):
        data = BytesIO(b'foobar')
        resp = Response(data)
        assert resp.response == data
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert next(result) == b'foobar'

    def test_file_response_w_file_wrapper(self):
        data = BytesIO(b'foobar')
        resp = Response(data)
        assert resp.response == data
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))

        file_wrapper = self.mock()
        self.expect(file_wrapper(data, resp.block_size)).result('DUMMY')
        self.replay()

        result = resp({'REQUEST_METHOD': 'GET',
                       'wsgi.file_wrapper': file_wrapper}, start_response)
        assert result == 'DUMMY'
    def test_file_response_content_length(self):
        data = BytesIO(b'*' * 342)
        resp = Response(data)
        assert resp.response == data
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert resp.content_length == 342
