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

"""
Service requests (parsing, handling, etc).
"""
import cgi

from mapproxy.util.py import cached_property
from mapproxy.compat import iteritems, PY2, text_type

if PY2:
    from urllib import quote
else:
    from urllib.parse import quote

class NoCaseMultiDict(dict):
    """
    This is a dictionary that allows case insensitive access to values.

    >>> d = NoCaseMultiDict([('A', 'b'), ('a', 'c'), ('B', 'f'), ('c', 'x'), ('c', 'y'), ('c', 'z')])
    >>> d['a']
    'b'
    >>> d.get_all('a')
    ['b', 'c']
    >>> 'a' in d and 'b' in d
    True
    """
    def _gen_dict(self, mapping=()):
        """A `NoCaseMultiDict` can be constructed from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        tmp = {}
        if isinstance(mapping, NoCaseMultiDict):
            for key, value in mapping.iteritems(): #pylint: disable-msg=E1103
                tmp.setdefault(key.lower(), (key, []))[1].extend(value)
        else:
            if isinstance(mapping, dict):
                itr = iteritems(mapping)
            else:
                itr = iter(mapping)
            for key, value in itr:
                tmp.setdefault(key.lower(), (key, []))[1].append(value)
        return tmp

    def __init__(self, mapping=()):
        """A `NoCaseMultiDict` can be constructed from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        dict.__init__(self, self._gen_dict(mapping))

    def update(self, mapping=(), append=False):
        """A `NoCaseMultiDict` can be updated from an iterable of
        ``(key, value)`` tuples or a dict.
        """
        for _, (key, values) in iteritems(self._gen_dict(mapping)):
            self.set(key, values, append=append, unpack=True)

    def __getitem__(self, key):
        """
        Return the first data value for this key.

        :raise KeyError: if the key does not exist
        """
        if key in self:
            return dict.__getitem__(self, key.lower())[1][0]
        raise KeyError(key)

    def __setitem__(self, key, value):
        dict.setdefault(self, key.lower(), (key, []))[1][:] = [value]

    def __delitem__(self, key):
        dict.__delitem__(self, key.lower())

    def __contains__(self, key):
        return dict.__contains__(self, key.lower())

    def __getstate__(self):
        data = []
        for key, values in self.iteritems():
            for v in values:
                data.append((key, v))
        return data

    def __setstate__(self, data):
        self.__init__(data)

    def get(self, key, default=None, type_func=None):
        """Return the default value if the requested data doesn't exist.
        If `type_func` is provided and is a callable it should convert the value,
        return it or raise a `ValueError` if that is not possible.  In this
        case the function will return the default as if the value was not
        found.

        Example:

        >>> d = NoCaseMultiDict(dict(foo='42', bar='blub'))
        >>> d.get('foo', type_func=int)
        42
        >>> d.get('bar', -1, type_func=int)
        -1
        """
        try:
            rv = self[key]
            if type_func is not None:
                rv = type_func(rv)
        except (KeyError, ValueError):
            rv = default
        return rv

    def get_all(self, key):
        """
        Return all values for the key as a list. Returns an empty list, if
        the key doesn't exist.
        """
        if key in self:
            return dict.__getitem__(self, key.lower())[1]
        else:
            return []

    def set(self, key, value, append=False, unpack=False):
        """
        Set a `value` for the `key`. If `append` is ``True`` the value will be added
        to other values for this `key`.

        If `unpack` is True, `value` will be unpacked and each item will be added.
        """
        if key in self:
            if not append:
                dict.__getitem__(self, key.lower())[1][:] = []
        else:
            dict.__setitem__(self, key.lower(), (key, []))
        if unpack:
            for v in value:
                dict.__getitem__(self, key.lower())[1].append(v)
        else:
            dict.__getitem__(self, key.lower())[1].append(value)

    def iteritems(self):
        """
        Iterates over all keys and values.
        """
        if PY2:
            for _, (key, values) in dict.iteritems(self):
                yield key, values
        else:
            for _, (key, values) in dict.items(self):
                yield key, values

    def copy(self):
        """
        Returns a copy of this object.
        """
        return self.__class__(self)

    def __repr__(self):
        tmp = []
        for key, values in self.iteritems():
            tmp.append((key, values))
        return '%s(%r)' % (self.__class__.__name__, tmp)


def url_decode(qs, charset='utf-8', decode_keys=False, include_empty=True,
               errors='ignore'):
    """
    Parse query string `qs` and return a `NoCaseMultiDict`.
    """
    tmp = []
    for key, value in cgi.parse_qsl(qs, include_empty):
        if PY2:
            if decode_keys:
                key = key.decode(charset, errors)
            tmp.append((key, value.decode(charset, errors)))
        else:
            if not isinstance(key, text_type):
                key = key.decode(charset, errors)
            if not isinstance(value, text_type):
                value = value.decode(charset, errors)
            tmp.append((key, value))
    return NoCaseMultiDict(tmp)

class Request(object):
    charset = 'utf8'

    def __init__(self, environ):
        self.environ = environ
        self.environ['mapproxy.request'] = self

        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            del environ['HTTP_X_SCRIPT_NAME']
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

    @cached_property
    def args(self):
        if self.environ.get('QUERY_STRING'):
            return url_decode(self.environ['QUERY_STRING'], self.charset)
        else:
            return {}

    @property
    def path(self):
        path = self.environ.get('PATH_INFO', '')
        if PY2:
            return path
        if path and isinstance(path, bytes):
            path = path.decode('utf-8')
        return path

    def pop_path(self):
        path = self.path.lstrip('/')
        if '/' in path:
            result, rest = path.split('/', 1)
            self.environ['PATH_INFO'] = '/' + rest
        else:
            self.environ['PATH_INFO'] = ''
            result = path
        if result:
            self.environ['SCRIPT_NAME'] = self.environ['SCRIPT_NAME'] + '/' + result
        return result

    @cached_property
    def host(self):
        if 'HTTP_X_FORWARDED_HOST' in self.environ:
            # might be a list, return first host only
            host = self.environ['HTTP_X_FORWARDED_HOST']
            host = host.split(',', 1)[0].strip()
            return host
        elif 'HTTP_HOST' in self.environ:
            host = self.environ['HTTP_HOST']
            if ':' in host:
                port = host.split(':')[1]
                if ((self.url_scheme, port) in (('https', '443'), ('http', '80'))):
                    host = host.split(':')[0]
            return host
        result = self.environ['SERVER_NAME']
        if ((self.url_scheme, self.environ['SERVER_PORT'])
            not in (('https', '443'), ('http', '80'))):
            result += ':' + self.environ['SERVER_PORT']
        return result

    @cached_property
    def url_scheme(self):
        scheme = self.environ.get('HTTP_X_FORWARDED_PROTO')
        if not scheme:
            scheme = self.environ['wsgi.url_scheme']
        return scheme

    @cached_property
    def host_url(self):
        return '%s://%s/' % (self.url_scheme, self.host)

    @property
    def script_url(self):
        "Full script URL without trailing /"
        return (self.host_url.rstrip('/') +
                quote(self.environ.get('SCRIPT_NAME', '/').rstrip('/'))
               )

    @property
    def base_url(self):
        return (self.host_url.rstrip('/')
                + quote(self.environ.get('SCRIPT_NAME', '').rstrip('/'))
                + quote(self.environ.get('PATH_INFO', ''))
               )

class RequestParams(object):
    """
    This class represents key-value request parameters. It allows case-insensitive
    access to all keys. Multiple values for a single key will be concatenated
    (eg. to ``layers=foo&layers=bar`` becomes ``layers: foo,bar``).

    All values can be accessed as a property.

    :param param: A dict or ``NoCaseMultiDict``.
    """
    params = None
    def __init__(self, param=None):
        self.delimiter = ','

        if param is None:
            self.params = NoCaseMultiDict()
        else:
            self.params = NoCaseMultiDict(param)

    def __str__(self):
        return self.query_string

    def get(self, key, default=None, type_func=None):
        """
        Returns the value for `key` or the `default`. `type_func` is called on the
        value to alter the value (e.g. use ``type_func=int`` to get ints).
        """
        return self.params.get(key, default, type_func)

    def set(self, key, value, append=False, unpack=False):
        """
        Set a `value` for the `key`. If `append` is ``True`` the value will be added
        to other values for this `key`.

        If `unpack` is True, `value` will be unpacked and each item will be added.
        """
        self.params.set(key, value, append=append, unpack=unpack)

    def update(self, mapping=(), append=False):
        """
        Update internal request parameters from an iterable of ``(key, value)``
        tuples or a dict.

        If `append` is ``True`` the value will be added to other values for
        this `key`.
        """
        self.params.update(mapping, append=append)

    def __getattr__(self, name):
        if name in self:
            return self[name]
        else:
            raise AttributeError("'%s' object has no attribute '%s" %
                                 (self.__class__.__name__, name))

    def __getitem__(self, key):
        return self.delimiter.join(map(text_type, self.params.get_all(key)))

    def __setitem__(self, key, value):
        """
        Set `value` for the `key`. Does not append values (see ``MapRequest.set``).
        """
        self.set(key, value)

    def __delitem__(self, key):
        if key in self:
            del self.params[key]


    def iteritems(self):
        for key, values in self.params.iteritems():
            yield key, self.delimiter.join((text_type(x) for x in values))

    def __contains__(self, key):
        return self.params and key in self.params

    def copy(self):
        return self.__class__(self.params)

    @property
    def query_string(self):
        """
        The map request as a query string (the order is not guaranteed).

        >>> qs = RequestParams(dict(foo='egg', bar='ham%eggs', baz=100)).query_string
        >>> sorted(qs.split('&'))
        ['bar=ham%25eggs', 'baz=100', 'foo=egg']
        """
        kv_pairs = []
        for key, values in self.params.iteritems():
            value = ','.join(text_type(v) for v in values)
            kv_pairs.append(key + '=' + quote(value.encode('utf-8'), safe=','))
        return '&'.join(kv_pairs)

    def with_defaults(self, defaults):
        """
        Return this MapRequest with all values from `defaults` overwritten.
        """
        new = self.copy()
        for key, value in defaults.params.iteritems():
            if value != [None]:
                new.set(key, value, unpack=True)
        return new

class BaseRequest(object):
    """
    This class represents a request with a URL and key-value parameters.

    :param param: A dict, `NoCaseMultiDict` or ``RequestParams``.
    :param url: The service URL for the request.
    :param validate: True if the request should be validated after initialization.
    """
    request_params = RequestParams

    def __init__(self, param=None, url='', validate=False, http=None):
        self.delimiter = ','
        self.http = http

        if param is None:
            self.params = self.request_params(NoCaseMultiDict())
        else:
            if isinstance(param, RequestParams):
                self.params = self.request_params(param.params)
            else:
                self.params = self.request_params(NoCaseMultiDict(param))
        self.url = url
        if validate:
            self.validate()

    def __str__(self):
        return self.complete_url

    def validate(self):
        pass

    @property
    def raw_params(self):
        params = {}
        for key, value in iteritems(self.params):
            params[key] = value
        return params


    @property
    def query_string(self):
        return self.params.query_string

    @property
    def complete_url(self):
        """
        The complete MapRequest as URL.
        """
        if not self.url:
            return self.query_string
        delimiter = '?'
        if '?' in self.url:
            delimiter = '&'
        if self.url[-1] == '?':
            delimiter = ''
        return self.url + delimiter + self.query_string

    def copy_with_request_params(self, req):
        """
        Return a copy of this request ond overwrite all param values from `req`.
        Use this method for templates
        (``req_template.copy_with_request_params(actual_values)``).
        """
        new_params = req.params.with_defaults(self.params)
        return self.__class__(param=new_params, url=self.url)

    def __repr__(self):
        return '%s(param=%r, url=%r)' % (self.__class__.__name__, self.params, self.url)

def split_mime_type(mime_type):
    """
    >>> split_mime_type('text/xml; charset=utf-8')
    ('text', 'xml', 'charset=utf-8')
    """
    options = None
    mime_class = None
    if '/' in mime_type:
        mime_class, mime_type = mime_type.split('/', 1)
    if ';' in mime_type:
        mime_type, options = [part.strip() for part in mime_type.split(';', 2)]
    return mime_class, mime_type, options

