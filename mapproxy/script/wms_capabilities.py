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
from __future__ import with_statement

import sys
import optparse
from cStringIO import StringIO
from xml.etree import ElementTree as etree

from mapproxy.client.http import open_url, HTTPClientError

class PrettyPrinter(object):
    def __init__(self, indent=4):
        self.indent = indent
        self.print_order = ['name', 'title', 'url', 'srs', 'llbbox', 'bbox']
        self.marker = '- '

    def print_line(self, indent, key, value=None, mark_first=False):
        marker = ''
        if value is None:
            value = ''
        if mark_first:
            indent = indent - len(self.marker)
            marker = self.marker
        print "%s%s%s: %s" % (' '*indent, marker, key, value)

    def _format_output(self, key, value, indent, mark_first=False):
        if key == 'bbox':
            self.print_line(indent, key)
            for srs_code, bbox in value.iteritems():
                self.print_line(indent+self.indent, srs_code, value=bbox, mark_first=mark_first)
        else:
            if isinstance(value, set):
                value = list(value)
            self.print_line(indent, key, value=value, mark_first=mark_first)

    def print_layers(self, layer_list, indent=None, root=False):
        if root:
            print 'Root-Layer:'

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
            for key, value in layer.iteritems():
                if key in self.print_order or key == 'layers':
                    continue
                self._format_output(key, value, indent)
            # print the sublayers now
            if layer.get('layers', False):
                self.print_line(indent, 'layers')
                self.print_layers(layer['layers'] , indent=indent+self.indent)

class CapabilitiesParserError(Exception):
    pass

class WMS111Capabilities(object):
    def __init__(self, capabilities):
        self.capabilities = capabilities
        self.tree = self._parse_capabilities()

    def _parse_capabilities(self):
        try:
            tree = etree.parse(self.capabilities)
        except Exception, ex:
             # catch all, etree.ParseError only avail since Python 2.7
             # 2.5 and 2.6 raises exc from underlying implementation like expat
            raise CapabilitiesParserError('Could not parse the document (%s)' %
             (ex.args[0],))
        return tree

    def metadata(self):
        # TODO remove method? currently not used
        name = self.tree.findtext('Service/Name')
        title = self.tree.findtext('Service/Title')
        abstract = self.tree.findtext('Service/Abstract')
        return dict(name=name, title=title, abstract=abstract)

    def layers(self):
        #catch errors
        root_layer = self.tree.find('Capability/Layer')
        if root_layer is None:
            raise CapabilitiesParserError('Could not parse a valid Capabilities document (Capability element not found).')
        try:
            layers = self.parse_layers(root_layer, {})
        except KeyError, ex:
            #raise own error
            raise CapabilitiesParserError('XML-Element has no such attribute (%s).' %
             (ex.args[0],))
        return layers

    def requests(self):
        requests_elem = self.tree.find('Capability/Request')
        resource = requests_elem.find('GetMap/DCPType/HTTP/Get/OnlineResource')
        return resource.attrib['{http://www.w3.org/1999/xlink}href']

    def parse_layers(self, root_layer, parent_layer):
        layers = []
        layer_dict = self.parse_layer(root_layer, parent_layer)
        layers.append(layer_dict)
        sub_layers = root_layer.findall('Layer')
        layer_dict['layers'] = []
        for layer in sub_layers:
            layer_dict['layers'].extend(self.parse_layers(layer, layer_dict))

        return layers

    def parse_layer(self, layer_elem, parent_layer):
        this_layer = dict(
            queryable=bool(layer_elem.attrib.get('queryable', 0)),
            opaque=bool(layer_elem.attrib.get('opaque', 0)),
            title=layer_elem.findtext('Title'),
            name=layer_elem.findtext('Name'),
        )
        llbbox_elem = layer_elem.find('LatLonBoundingBox')
        llbbox = None
        if llbbox_elem is not None:
            llbbox = (
                llbbox_elem.attrib['minx'],
                llbbox_elem.attrib['miny'],
                llbbox_elem.attrib['maxx'],
                llbbox_elem.attrib['maxy']
            )
            llbbox = map(float, llbbox)
        this_layer['llbbox'] = llbbox
        this_layer['url'] = self.requests()

        srs_elements = layer_elem.findall('SRS')
        srs_codes = set([srs.text for srs in srs_elements])
        # unique srs-codes in either srs or parent_layer['srs']
        this_layer['srs'] = srs_codes | parent_layer.get('srs', set())

        bbox_elements = layer_elem.findall('BoundingBox')
        bbox = {}
        for bbox_elem in bbox_elements:
            key = bbox_elem.attrib['SRS']
            values = [
                bbox_elem.attrib['minx'],
                bbox_elem.attrib['miny'],
                bbox_elem.attrib['maxx'],
                bbox_elem.attrib['maxy']
            ]
            values = map(float, values)
            bbox[key] = values
        this_layer['bbox'] = bbox

        return this_layer

def log_error(msg, *args):
    print >>sys.stderr, msg % args

def parse_capabilities(capabilities_url):
    try:
        capabilities_response = open_url(capabilities_url)
    except HTTPClientError, ex:
        log_error('ERROR: %s', ex.args[0])
        sys.exit(1)

    # after parsing capabilities_response will be empty, therefore cache it
    capabilities = StringIO(capabilities_response.read())

    try:
        wms_capabilities = WMS111Capabilities(capabilities)
        wms_capabilities.layers()
    except CapabilitiesParserError, ex:
        log_error('%s\n%s\n%s\n%s\n%s', 'Recieved document:', '-'*80, capabilities.getvalue(), '-'*80, ex.message)
        sys.exit(1)

    print "# Note: This is not a valid MapProxy configuration!"

    printer = PrettyPrinter(indent=4)
    printer.print_layers(wms_capabilities.layers(), root=True)

def wms_capabilities_command(args=None):
    parser = optparse.OptionParser("%prog wms-capabilities [options] URL",
        description="Read and parse WMS 1.1.1 capabilities and print out"
        " information about each layer. It does _not_ return a valid"
        " MapProxy configuration.")
    parser.add_option("--host", dest="capabilites_url",
        help="WMS Capabilites URL")

    if args:
        args = args[1:] # remove script name

    (options, args) = parser.parse_args(args)
    if not options.capabilites_url:
        if len(args) != 1:
            parser.print_help()
            sys.exit(2)
        else:
            options.capabilites_url = args[0]

    parse_capabilities(options.capabilites_url)