# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from __future__ import print_function

import sys
import optparse

from mapproxy.compat import iteritems, BytesIO
from mapproxy.compat.modules import urlparse
from mapproxy.client.http import open_url, HTTPClientError
from mapproxy.request.base import BaseRequest, url_decode
from mapproxy.util.ext import wmsparse


class PrettyPrinter(object):
    def __init__(self, indent=4, version='1.1.1'):
        self.indent = indent
        self.print_order = ['name', 'title', 'url', 'srs', 'llbbox', 'bbox']
        self.marker = '- '
        self.version = version

    def print_line(self, indent, key, value=None, mark_first=False):
        marker = ''
        if value is None:
            value = ''
        if mark_first:
            indent = indent - len(self.marker)
            marker = self.marker
        print(("%s%s%s: %s" % (' '*indent, marker, key, value)))

    def _format_output(self, key, value, indent, mark_first=False):
        if key == 'bbox':
            self.print_line(indent, key)
            for srs_code, bbox in iteritems(value):
                self.print_line(indent+self.indent, srs_code, value=bbox, mark_first=mark_first)
        else:
            if isinstance(value, set):
                value = list(value)
            self.print_line(indent, key, value=value, mark_first=mark_first)

    def print_layers(self, capabilities, indent=None, root=False):
        if root:
            print("# Note: This is not a valid MapProxy configuration!")
            print('Capabilities Document Version %s' % (self.version,))
            print('Root-Layer:')
            layer_list = capabilities.layers()['layers']
        else:
            layer_list = capabilities['layers']

        indent = indent or self.indent
        for layer in layer_list:
            marked_first = False
            # print ordered items first
            for item in self.print_order:
                if layer.get(item, False):
                    if not marked_first:
                        marked_first = True
                        self._format_output(item, layer[item], indent, mark_first=marked_first)
                    else:
                        self._format_output(item, layer[item], indent)
            # print remaining items except sublayers
            for key, value in iteritems(layer):
                if key in self.print_order or key == 'layers':
                    continue
                self._format_output(key, value, indent)
            # print the sublayers now
            if layer.get('layers', False):
                self.print_line(indent, 'layers')
                self.print_layers(layer, indent=indent+self.indent)

def log_error(msg, *args):
    print(msg % args, file=sys.stderr)

def wms_capapilities_url(url, version):
    parsed_url = urlparse.urlparse(url)
    base_req = BaseRequest(
        url=url.split('?', 1)[0],
        param=url_decode(parsed_url.query),
    )

    base_req.params['service'] = 'WMS'
    base_req.params['version'] = version
    base_req.params['request'] = 'GetCapabilities'
    return base_req.complete_url

def parse_capabilities(fileobj, version='1.1.1'):
    try:
        return wmsparse.parse_capabilities(fileobj)
    except ValueError as ex:
        log_error('%s\n%s\n%s\n%s\nNot a capabilities document: %s', 'Recieved document:', '-'*80, fileobj.getvalue(), '-'*80, ex.args[0])
        sys.exit(1)
    except Exception as ex:
        # catch all, etree.ParseError only avail since Python 2.7
        # 2.5 and 2.6 raises exc from underlying implementation like expat
        log_error('%s\n%s\n%s\n%s\nCould not parse the document: %s', 'Recieved document:', '-'*80, fileobj.getvalue(), '-'*80, ex.args[0])
        sys.exit(1)

def parse_capabilities_url(url, version='1.1.1'):
    try:
        capabilities_url = wms_capapilities_url(url, version)
        capabilities_response = open_url(capabilities_url)
    except HTTPClientError as ex:
        log_error('ERROR: %s', ex.args[0])
        sys.exit(1)

    # after parsing capabilities_response will be empty, therefore cache it
    capabilities = BytesIO(capabilities_response.read())
    return parse_capabilities(capabilities, version=version)

def wms_capabilities_command(args=None):
    parser = optparse.OptionParser("%prog wms-capabilities [options] URL",
        description="Read and parse WMS 1.1.1 capabilities and print out"
        " information about each layer. It does _not_ return a valid"
        " MapProxy configuration.")
    parser.add_option("--host", dest="capabilities_url",
        help="WMS Capabilites URL")
    parser.add_option("--version", dest="version",
        choices=['1.1.1', '1.3.0'], default='1.1.1', help="Request GetCapabilities-document in version 1.1.1 or 1.3.0", metavar="<1.1.1 or 1.3.0>")

    if args:
        args = args[1:] # remove script name

    (options, args) = parser.parse_args(args)
    if not options.capabilities_url:
        if len(args) != 1:
            parser.print_help()
            sys.exit(2)
        else:
            options.capabilities_url = args[0]

    try:
        service = parse_capabilities_url(options.capabilities_url, version=options.version)

        printer = PrettyPrinter(indent=4, version=options.version)
        printer.print_layers(service, root=True)

    except KeyError as ex:
        log_error('XML-Element has no such attribute (%s).' % (ex.args[0],))
        sys.exit(1)
