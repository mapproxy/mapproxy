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

import urlparse
import sys
import optparse
from cStringIO import StringIO
from xml.etree import ElementTree as etree
from xml.etree.ElementTree import XMLParser

from mapproxy.client.http import open_url, HTTPClientError
from mapproxy.request.base import BaseRequest, url_decode

ENCODING = sys.getdefaultencoding()
if ENCODING in (None, 'ascii'):
    ENCODING = 'UTF-8'

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
        print ("%s%s%s: %s" % (' '*indent, marker, key, value)).encode(ENCODING)

    def _format_output(self, key, value, indent, mark_first=False):
        if key == 'bbox':
            self.print_line(indent, key)
            for srs_code, bbox in value.iteritems():
                self.print_line(indent+self.indent, srs_code, value=bbox, mark_first=mark_first)
        else:
            if isinstance(value, set):
                value = list(value)
            self.print_line(indent, key, value=value, mark_first=mark_first)

    def print_layers(self, capabilities, indent=None, root=False):
        if root:
            print "# Note: This is not a valid MapProxy configuration!"
            print 'Capabilities Document Version %s' % (self.version,)
            print 'Root-Layer:'
            layer_list = capabilities['layer']['layers']
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
            for key, value in layer.iteritems():
                if key in self.print_order or key == 'layers':
                    continue
                self._format_output(key, value, indent)
            # print the sublayers now
            if layer.get('layers', False):
                self.print_line(indent, 'layers')
                self.print_layers(layer, indent=indent+self.indent)

class CapabilitiesParserError(Exception):
    pass

class CapabilitiesVersionError(Exception):
    pass

class UTF8XMLParser(XMLParser):
    def __init__(self, *args, **kw):
        super(XMLParser, self).__init__(*args, **kw)

class WMSCapabilitiesParserBase(object):
    def __init__(self, capabilities):
        self.capabilities = capabilities
        self.tree = self._parse_capabilities()
        self.prefix = self._prefix()
        self._check_valid_document()

    def _parse_capabilities(self):
        try:
            tree = etree.parse(self.capabilities)
        except Exception, ex:
            # catch all, etree.ParseError only avail since Python 2.7
            # 2.5 and 2.6 raises exc from underlying implementation like expat
            raise CapabilitiesParserError('Could not parse the document (%s)' %
                (ex.args[0],))
        return tree

    def _check_valid_document(self):
        layer_elem = self.tree.find(self._namespace_path('Capability'))
        if layer_elem is None:
            raise CapabilitiesParserError('Could not parse a valid Capabilities document (Capability element not found).')

    def _prefix(self):
        return ''

    def _namespace_path(self, path):
        # add prefix to all further elements
        path = path.replace('/', '/%s' % (self.prefix,))
        # and before the first element
        path = '%s%s' % (self.prefix, path)
        return path

    def metadata(self):
        name = self.tree.findtext(self._namespace_path('Service/Name'))
        title = self.tree.findtext(self._namespace_path('Service/Title'))
        abstract = self.tree.findtext(self._namespace_path('Service/Abstract'))
        return dict(name=name, title=title, abstract=abstract)

    def root_layer(self):
        layer_elem = self.tree.find(self._namespace_path('Capability/Layer'))
        if layer_elem is None:
            raise CapabilitiesParserError('Could not parse a valid Capabilities document (Capability element not found).') 
        return self.layers(layer_elem)

    def service(self):
        metadata = self.metadata()
        url = self.requests()
        root_layer = self.root_layer()
        service = {
            'title': metadata['title'],
            'abstract': metadata['abstract'],
            # todo add more metadata,
            'url': url,
            'layer': root_layer,
        }
        return service

    def layers(self, layer_elem):
        try:
            layers = self._layers(layer_elem, parent_layer={})
        except KeyError, ex:
            #raise own error
            raise CapabilitiesParserError('XML-Element has no such attribute (%s).' %
             (ex.args[0],))
        return layers

    def requests(self):
        requests_elem = self.tree.find(self._namespace_path('Capability/Request'))
        resource = requests_elem.find(self._namespace_path('GetMap/DCPType/HTTP/Get/OnlineResource'))
        return resource.attrib['{http://www.w3.org/1999/xlink}href']

    def _layers(self, layer_elem, parent_layer):
        this_layer = self._layer(layer_elem, parent_layer)
        sub_layers = layer_elem.findall(self._namespace_path('Layer'))
        if sub_layers:
            this_layer['layers'] = []
            for layer in sub_layers:
                this_layer['layers'].append(self._layers(layer, this_layer))

        return this_layer
        
    def _layer(self, layer_elem, parent_layer):
        raise NotImplementedError()

class WMS111CapabilitiesParser(WMSCapabilitiesParserBase):
    def _layer(self, layer_elem, parent_layer):
        this_layer = dict(
            queryable=bool(layer_elem.attrib.get('queryable', 0)),
            opaque=bool(layer_elem.attrib.get('opaque', 0)),
            title=layer_elem.findtext('Title').strip(),
            name=layer_elem.findtext('Name', '').strip() or None,
            abstract=layer_elem.findtext('Abstract', '').strip() or None, 
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

class WMS130CapabilitiesParser(WMSCapabilitiesParserBase):
    def _prefix(self):
        return '{http://www.opengis.net/wms}'

    def _layer(self, layer_elem, parent_layer):
        this_layer = dict(
            queryable=bool(layer_elem.attrib.get('queryable', 0)),
            opaque=bool(layer_elem.attrib.get('opaque', 0)),
            title=layer_elem.findtext(self._namespace_path('Title')).strip(),
            name=layer_elem.findtext(self._namespace_path('Name'), '').strip() or None,
            abstract=layer_elem.findtext(self._namespace_path('Abstract'), '').strip() or None,
        )
        llbbox_elem = layer_elem.find(self._namespace_path('EX_GeographicBoundingBox'))
        llbbox = None
        if llbbox_elem is not None:
            llbbox = (
                llbbox_elem.find(self._namespace_path('westBoundLongitude')).text,
                llbbox_elem.find(self._namespace_path('southBoundLatitude')).text,
                llbbox_elem.find(self._namespace_path('eastBoundLongitude')).text,
                llbbox_elem.find(self._namespace_path('northBoundLatitude')).text
            )
            llbbox = map(float, llbbox)
        this_layer['llbbox'] = llbbox
        this_layer['url'] = self.requests()

        srs_elements = layer_elem.findall(self._namespace_path('CRS'))
        srs_codes = set([srs.text for srs in srs_elements])
        # unique srs-codes in either srs or parent_layer['srs']
        this_layer['srs'] = srs_codes | parent_layer.get('srs', set())

        bbox_elements = layer_elem.findall(self._namespace_path('BoundingBox'))
        bbox = {}
        for bbox_elem in bbox_elements:
            key = bbox_elem.attrib['CRS']
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
    print >>sys.stderr, (msg % args).encode(ENCODING)

def wms_capapilities_url(url, version):
    parsed_url = urlparse.urlparse(url)
    base_req = BaseRequest(
        url=url.split('?', 1)[0],
        param=url_decode(parsed_url.params),
    )

    base_req.params['service'] = 'WMS'
    base_req.params['version'] = version
    base_req.params['request'] = 'GetCapabilities'
    return base_req.complete_url

def parse_capabilities(fileobj, version='1.1.1'):
    try:
        if version == '1.1.1':
            wms_capabilities = WMS111CapabilitiesParser(fileobj)
        elif version == '1.3.0':
            wms_capabilities = WMS130CapabilitiesParser(fileobj)
        else:
            raise CapabilitiesVersionError('Version not supported: %s' % (version,))
        service = wms_capabilities.service()
    except CapabilitiesParserError, ex:
        log_error('%s\n%s\n%s\n%s\n%s', 'Recieved document:', '-'*80, fileobj.getvalue(), '-'*80, ex.message)
        sys.exit(1)
    except CapabilitiesVersionError, ex:
        log_error(ex.message)
        sys.exit(1)

    return service

def parse_capabilities_url(url, version='1.1.1'):
    try:
        capabilities_url = wms_capapilities_url(url, version)
        capabilities_response = open_url(capabilities_url)
    except HTTPClientError, ex:
        log_error('ERROR: %s', ex.args[0])
        sys.exit(1)

    # after parsing capabilities_response will be empty, therefore cache it
    capabilities = StringIO(capabilities_response.read())
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

    service = parse_capabilities_url(options.capabilities_url, version=options.version)

    printer = PrettyPrinter(indent=4, version=options.version)
    printer.print_layers(service, root=True)