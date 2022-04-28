# Copyright (c) 2011, Oliver Tonnhofer <olt@omniscale.de>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import re
from contextlib import contextmanager

from .spec import required, one_of, anything, recursive
from mapproxy.compat import iteritems, iterkeys, text_type

class Context(object):
    def __init__(self):
        self.recurse_spec = None
        self.obj_pos = []

    def push(self, spec):
        self.obj_pos.append(spec)

    def pop(self):
        return self.obj_pos.pop()

    @contextmanager
    def pos(self, spec):
        self.push(spec)
        yield
        self.pop()

    @property
    def current_pos(self):
        return ''.join(self.obj_pos).lstrip('.') or '.'

def validate(spec, data):
    """
    Validate `data` against `spec`.
    """
    return Validator(spec).validate(data)

class ValidationError(TypeError):
    def __init__(self, msg, errors=None, informal_only=False):
        TypeError.__init__(self, msg)
        self.informal_only = informal_only
        self.errors = errors or []

class SpecError(TypeError):
    pass

class Validator(object):
    def __init__(self, spec, fail_fast=False):
        """
        :params fail_fast: True if it should raise on the first error
        """
        self.context = Context()
        self.complete_spec = spec
        self.raise_first_error = fail_fast
        self.errors = False
        self.messages = []

    def validate(self, data):
        self._validate_part(self.complete_spec, data)

        if self.messages:
            if len(self.messages) == 1:
                raise ValidationError(self.messages[0], self.messages, informal_only=not self.errors)
            else:
                raise ValidationError('found %d validation errors.' % len(self.messages), self.messages,
                    informal_only=not self.errors)

    def _validate_part(self, spec, data):
        if hasattr(spec, 'subspec'):
            try:
                spec = spec.subspec(data, self.context)
            except ValueError as ex:
                return self._handle_error(str(ex))

        if isinstance(spec, recursive):
            if spec.spec:
                self.context.recurse_spec = spec.spec
                self._validate_part(spec.spec, data)
                self.context.recurse_spec = None
                return
            else:
                spec = self.context.recurse_spec
                if spec is None:
                    raise SpecError('found recursive() outside recursive spec')

        if isinstance(spec, anything):
            return

        if data is None:
            data = {}

        if isinstance(spec, one_of):
            # check if at least one spec type matches
            for subspec in spec.specs:
                if type_matches(subspec, data):
                    self._validate_part(subspec, data)
                    return
            else:
                return self._handle_error("%r in %s not of any type %s" %
                    (data, self.context.current_pos, ', '.join(map(type_str, spec.specs))))
        elif not type_matches(spec, data):
            return self._handle_error("%r in %s not of type %s" %
                (data, self.context.current_pos, type_str(spec)))

        # recurse in dicts and lists
        if isinstance(spec, dict):
            self._validate_dict(spec, data)
        elif isinstance(spec, list):
            self._validate_list(spec, data)

    def _validate_dict(self, spec, data):
        accept_any_key = False
        any_key_spec = None
        for k in iterkeys(spec):
            if isinstance(k, required):
                if k not in data:
                    self._handle_error("missing '%s', not in %s" %
                        (k, self.context.current_pos))
            if isinstance(k, anything):
                accept_any_key = True
                any_key_spec = spec[k]

        for k, v in iteritems(data):
            if accept_any_key:
                with self.context.pos('.' + text_type(k)):
                    self._validate_part(any_key_spec, v)

            else:
                if k not in spec:
                    self._handle_error("unknown '%s' in %s" %
                        (k, self.context.current_pos), info_only=True)
                    continue
                with self.context.pos('.' + text_type(k)):
                    self._validate_part(spec[k], v)

    def _validate_list(self, spec, data):
        if not len(spec) == 1:
            raise SpecError('lists support only one type, got: %s' % spec)
        for i, v in enumerate(data):
            with self.context.pos('[%d]' % i):
                self._validate_part(spec[0], v)

    def _handle_error(self, msg, info_only=False):
        if not info_only:
            self.errors = True
        if self.raise_first_error and not info_only:
            raise ValidationError(msg)
        self.messages.append(msg)

def type_str(spec):
    if not isinstance(spec, type):
        spec = type(spec)

    match = re.match(r"<type '(\w+)'>", str(spec))
    if match:
        return match.group(1)

    match = re.match(r"<class '([\w._]+)'>", str(spec))
    if match:
        return match.group(1).split('.')[-1]

    return str(type)

def type_matches(spec, data):
    if hasattr(spec, 'compare_type'):
        return spec.compare_type(data)
    if isinstance(spec, type):
        spec_type = spec
    else:
        spec_type = type(spec)
    return isinstance(data, spec_type)

