from ..util import resolve_ns

from nose.tools import eq_

def test_resolve_ns():
    eq_(resolve_ns('/bar/bar', {}, None),
        '/bar/bar')

    eq_(resolve_ns('/bar/bar', {}, 'http://foo'),
        '/{http://foo}bar/{http://foo}bar')

    eq_(resolve_ns('/bar/xlink:bar', {'xlink': 'http://www.w3.org/1999/xlink'}, 'http://foo'),
        '/{http://foo}bar/{http://www.w3.org/1999/xlink}bar')

    eq_(resolve_ns('bar/xlink:bar', {'xlink': 'http://www.w3.org/1999/xlink'}, 'http://foo'),
        '{http://foo}bar/{http://www.w3.org/1999/xlink}bar')
