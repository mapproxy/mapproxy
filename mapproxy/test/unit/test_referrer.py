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

from webtest import TestApp

from mapproxy.response import Response
from mapproxy.security.referrer import ReferrerFilter, NONE, SELF, REGEX


DENIED=404

class CheckApp(object):
    def __init__(self):
        self._called = False
    
    def __call__(self, environ, start_response):
        self._called = True
        return Response('')(environ, start_response)
    
    @property
    def called(self):
        result = self._called
        self._called = False
        return result

class TestReferrerFilter(object):
    def setup(self):
        self.check_app = CheckApp()

    def test_no_referrer(self):
        app = TestApp(ReferrerFilter(self.check_app))
        app.get('/')
        assert self.check_app.called
    
    def test_none(self):
        app = TestApp(ReferrerFilter(self.check_app, [NONE]))
        app.get('/')
        assert self.check_app.called

        app.get('/', headers={'Referer': 'http://localhost/'}, status=DENIED)
        assert not self.check_app.called
    
    def test_string(self):
        referrer_filter = ['http://omniscale.de/', 'http://localhost/']
        
        for referrer, allowed in (('http://localhost/bar', True),
                                  ('http://localhost:5050/bar', False),
                                  ('http://omniscale.net', False)):
            yield self.check_referrer, referrer_filter, referrer, allowed
        

    def test_self(self):
        referrer_filter = [SELF]
        
        for referrer, allowed in ((None, False),
                                  ('http://localhost:80/', True),
                                  ('http://localhost/bar', True),
                                  ('http:/localhost:5050/', False)):
            yield self.check_referrer, referrer_filter, referrer, allowed
    
    def test_regex(self):
        referrer_filter = [REGEX('http://([ab]\.)?osm/')]
        
        for referrer, allowed in (
            (None, False),
            ('http://osm/', True),
            ('http://a.osm/', True),
            ('http://b.osm/', True),
            ('http://c.osm/', False),
            ):
            yield self.check_referrer, referrer_filter, referrer, allowed
    
    def check_referrer(self, filter, referrer_header, allowed):
        app = TestApp(ReferrerFilter(self.check_app, filter))
        headers = {}
        if referrer_header:
            headers['Referer'] = referrer_header
        status = None
        if not allowed:
            status = DENIED
    
        app.get('/', headers=headers, status=status)
    
        if allowed:
            assert self.check_app.called 
        else:
            assert not self.check_app.called
    