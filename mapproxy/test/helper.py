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

from __future__ import with_statement
import tempfile
import os
import re
from lxml import etree
import mocker

from nose.tools import eq_

class Mocker(object):
    """
    This is a base class for unit-tests that use ``mocker``. This class follows
    the nosetest naming conventions for setup and teardown methods.
    
    `setup` will initialize a `mocker.Mocker`. The `teardown` method
    will run ``mocker.verify()``.
    """
    def setup(self):
        self.mocker = mocker.Mocker()
    def expect_and_return(self, mock_call, return_val):
        """
        Register a return value for the mock call.
        :param return_val: The value mock_call should return.
        """
        self.mocker.result(return_val)
    def expect(self, mock_call):
        return mocker.expect(mock_call)
    def replay(self):
        """
        Finish mock-record phase.
        """
        self.mocker.replay()
    def mock(self, base_cls=None):
        """
        Return a new mock object.
        :param base_cls: check method signatures of the mock-calls with this
            base_cls signature (optional)
        """
        if base_cls:
            return self.mocker.mock(base_cls)
        return self.mocker.mock()
    def teardown(self):
        self.mocker.verify()

class TempFiles(object):
    """
    This class is a context manager for temporary files.
    
    >>> with TempFiles(n=2, suffix='.png') as tmp:
    ...     for f in tmp:
    ...         assert os.path.exists(f)
    >>> for f in tmp:
    ...     assert not os.path.exists(f)
    """
    def __init__(self, n=1, suffix='', no_create=False):
        self.n = n
        self.suffix = suffix
        self.no_create = no_create
        self.tmp_files = []
    
    def __enter__(self):
        for _ in range(self.n):
            fd, tmp_file = tempfile.mkstemp(suffix=self.suffix)
            os.close(fd)
            self.tmp_files.append(tmp_file)
            if self.no_create:
                os.remove(tmp_file)
        return self.tmp_files
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for tmp_file in self.tmp_files:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        self.tmp_files = []

class TempFile(TempFiles):
    def __init__(self, suffix='', no_create=False):
        TempFiles.__init__(self, suffix=suffix, no_create=no_create)
    def __enter__(self):
        return TempFiles.__enter__(self)[0]

class LogMock(object):
    log_methods = ('info', 'debug', 'warn', 'error', 'fail')
    def __init__(self, module, log_name='log'):
        self.module = module
        self.orig_logger = None
        self.logged_msgs = []
    
    def __enter__(self):
        self.orig_logger = self.module.log
        self.module.log = self
        return self
    
    def __getattr__(self, name):
        if name in self.log_methods:
            def _log(msg):
                self.logged_msgs.append((name, msg))
            return _log
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, name))
    
    def assert_log(self, type, msg):
        log_type, log_msg = self.logged_msgs.pop(0)
        assert log_type == type, 'expected %s log message, but was %s' % (type, log_type)
        assert msg in log_msg.lower(), "expected string '%s' in log message '%s'" % \
            (msg, log_msg)
        
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.module.log = self.orig_logger
    

def assert_re(value, regex):
    """
    >>> assert_re('hello', 'l+')
    >>> assert_re('hello', 'l{3}')
    Traceback (most recent call last):
        ...
    AssertionError: hello ~= l{3}
    """
    match = re.search(regex, value)
    assert match is not None, '%s ~= %s' % (value, regex)

def validate_with_dtd(doc, dtd_name, dtd_basedir=None):
    if dtd_basedir is None:
        dtd_basedir = os.path.join(os.path.dirname(__file__), 'schemas')
    
    dtd_filename = os.path.join(dtd_basedir, dtd_name)
    with open(dtd_filename) as schema:
        dtd = etree.DTD(schema)
        if isinstance(doc, basestring):
            xml = etree.XML(doc)
        else:
            xml = doc
        is_valid = dtd.validate(xml)
        print dtd.error_log.filter_from_errors()
        return is_valid

def validate_with_xsd(doc, xsd_name, xsd_basedir=None):
    if xsd_basedir is None:
        xsd_basedir = os.path.join(os.path.dirname(__file__), 'schemas')
    
    xsd_filename = os.path.join(xsd_basedir, xsd_name)
    
    with open(xsd_filename) as schema:
        xsd = etree.parse(schema)
        xml_schema = etree.XMLSchema(xsd)
        if isinstance(doc, basestring):
            xml = etree.XML(doc)
        else:
            xml = doc
        is_valid = xml_schema.validate(xml)
        print xml_schema.error_log.filter_from_errors()
        return is_valid

class XPathValidator(object):
    def __init__(self, doc):
        self.xml = etree.XML(doc)
    
    def assert_xpath(self, xpath, expected=None):
        assert len(self.xml.xpath(xpath)) > 0, xpath + ' does not match anything'
        if expected is not None:
            if callable(expected):
                assert expected(self.xml.xpath(xpath)[0])
            else:
                eq_(self.xml.xpath(xpath)[0], expected)
    def xpath(self, xpath):
        return self.xml.xpath(xpath)


def strip_whitespace(text):
    """
    >>> strip_whitespace(' <foo> bar\\n zing\\t1')
    '<foo>barzing1'
    """
    return re.sub('\s+', '', text)