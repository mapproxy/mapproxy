# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from cStringIO import StringIO

from mapproxy.tests.helper import Mocker
from mocker import ANY
from mapproxy.core.response import Response

class TestResponse(Mocker):
    def test_str_response(self):
        resp = Response('string content')
        assert isinstance(resp.response, basestring)
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert result.next() == 'string content'
    
    def test_itr_response(self):
        resp = Response(iter(['string content', 'as iterable']))
        assert hasattr(resp.response, 'next')
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert result.next() == 'string content'
        assert result.next() == 'as iterable'
    
    def test_file_response(self):
        data = StringIO('foobar')
        resp = Response(data)
        assert resp.response == data
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert result.next() == 'foobar'
    
    def test_file_response_w_file_wrapper(self):
        data = StringIO('foobar')
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
        data = StringIO('*' * 342)
        resp = Response(data)
        assert resp.response == data
        start_response = self.mock()
        self.expect(start_response('200 OK', ANY))
        self.replay()
        result = resp({'REQUEST_METHOD': 'GET'}, start_response)
        assert resp.content_length == 342
