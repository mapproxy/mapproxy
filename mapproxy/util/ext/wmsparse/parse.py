from __future__ import print_function
import math

from .util import resolve_ns

from xml.etree import ElementTree as etree
from mapproxy.compat import string_type
from mapproxy.request.wms import switch_bbox_epsg_axis_order


class WMSCapabilities(object):
    _default_namespace = None
    _namespaces = {
        'xlink': 'http://www.w3.org/1999/xlink',
    }

    version = None


    def __init__(self, tree):
        self.tree = tree
        self._layer_tree = None

    def resolve_ns(self, xpath):
        return resolve_ns(xpath, self._namespaces, self._default_namespace)

    def findtext(self, tree, xpath):
        return tree.findtext(self.resolve_ns(xpath))

    def find(self, tree, xpath):
        return tree.find(self.resolve_ns(xpath))

    def findall(self, tree, xpath):
        return tree.findall(self.resolve_ns(xpath))

    def attrib(self, elem, name):
        return elem.attrib[self.resolve_ns(name)]

    def metadata(self):
        md = dict(
            name = self.findtext(self.tree, 'Service/Name'),
            title = self.findtext(self.tree, 'Service/Title'),
            abstract = self.findtext(self.tree, 'Service/Abstract'),
            fees = self.findtext(self.tree, 'Service/Fees'),
            access_constraints = self.findtext(self.tree, 'Service/AccessConstraints'),
        )
        elem = self.find(self.tree, 'Service/OnlineResource')
        if elem is not None:
            md['online_resource'] = self.attrib(elem, 'xlink:href')

        md['contact'] = self.parse_contact()
        return md

    def parse_contact(self):
        elem = self.find(self.tree, 'Service/ContactInformation')
        if elem is None or len(elem) is 0:
            elem = etree.Element(None)
        md = dict(
            person = self.findtext(elem, 'ContactPersonPrimary/ContactPerson'),
            organization = self.findtext(elem, 'ContactPersonPrimary/ContactOrganization'),
            position = self.findtext(elem, 'ContactPosition'),

            address = self.findtext(elem, 'ContactAddress/Address'),
            city = self.findtext(elem, 'ContactAddress/City'),
            postcode = self.findtext(elem, 'ContactAddress/PostCode'),
            country = self.findtext(elem, 'ContactAddress/Country'),
            phone = self.findtext(elem, 'ContactVoiceTelephone'),
            fax = self.findtext(elem, 'ContactFacsimileTelephone'),
            email = self.findtext(elem, 'ContactElectronicMailAddress'),
        )

        return md


    def layers(self):
        if not self._layer_tree:
            root_layer = self.find(self.tree, 'Capability/Layer')
            self._layer_tree = self.parse_layer(root_layer, None)

        return self._layer_tree

    def layers_list(self):
        layers = []
        def append_layer(layer):
            if layer.get('name'):
                layers.append(layer)
            for child_layer in layer.get('layers', []):
                append_layer(child_layer)

        append_layer(self.layers())
        return layers

    def requests(self):
        requests_elem = self.find(self.tree, 'Capability/Request')
        resources = {}
        resource = self.find(requests_elem, 'GetMap/DCPType/HTTP/Get/OnlineResource')
        if resource != None:
            resources['GetMap'] = self.attrib(resource, 'xlink:href')
        return resources

    def parse_layer(self, layer_elem, parent_layer):
        child_layers = []
        layer = self.parse_layer_data(layer_elem, parent_layer or {})
        child_layer_elems = self.findall(layer_elem, 'Layer')

        for child_elem in child_layer_elems:
            child_layers.append(self.parse_layer(child_elem, layer))

        layer['layers'] = child_layers
        return layer

    def parse_layer_data(self, elem, parent_layer):
        layer = dict(
            queryable=elem.attrib.get('queryable') == '1',
            opaque=elem.attrib.get('opaque') == '1',
            title=self.findtext(elem, 'Title'),
            abstract=self.findtext(elem, 'Abstract'),
            name=self.findtext(elem, 'Name'),
        )

        layer['srs'] = self.layer_srs(elem, parent_layer)
        layer['res_hint'] = self.layer_res_hint(elem, parent_layer)
        layer['llbbox'] = self.layer_llbbox(elem, parent_layer)
        layer['bbox_srs'] = self.layer_bbox_srs(elem, parent_layer)
        layer['url'] = self.requests()['GetMap']
        layer['legend'] = self.layer_legend(elem)

        return layer

    def layer_legend(self, elem):
        style_elems = self.findall(elem, 'Style')
        legend_elem = None
        # we don't support styles, but will use the
        # LegendURL for the default style
        for elem in style_elems:
            if self.findtext(elem, 'Name') in ('default', ''):
                legend_elem = self.find(elem, 'LegendURL')
                break

        if legend_elem is None:
            return

        legend = {}
        legend_url = self.find(legend_elem, 'OnlineResource')
        legend['url'] = self.attrib(legend_url, 'xlink:href')
        return legend

    def layer_res_hint(self, elem, parent_layer):
        elem = self.find(elem, 'ScaleHint')
        if elem is None:
            return parent_layer.get('res_hint')
        # ScaleHints are the diagonal pixel resolutions
        # NOTE: max is not the maximum resolution, but the max
        # value, so it's actualy the min_res
        min_res = elem.attrib.get('max')
        max_res = elem.attrib.get('min')

        if min_res:
            min_res = math.sqrt(float(min_res) ** 2 / 2.0)
        if max_res:
            max_res = math.sqrt(float(max_res) ** 2 / 2.0)

        return min_res, max_res

class WMS111Capabilities(WMSCapabilities):
    version = '1.1.1'

    def layer_llbbox(self, elem, parent_layer):
        llbbox_elem = self.find(elem, 'LatLonBoundingBox')
        llbbox = None
        if llbbox_elem is not None:
            llbbox = (
                llbbox_elem.attrib['minx'],
                llbbox_elem.attrib['miny'],
                llbbox_elem.attrib['maxx'],
                llbbox_elem.attrib['maxy']
            )
            llbbox = [float(x) for x in llbbox]
        elif parent_layer and 'llbbox' in parent_layer:
            llbbox = parent_layer['llbbox']
        return llbbox

    def layer_srs(self, elem, parent_layer=None):
        srs_elements = self.findall(elem, 'SRS')
        srs_codes = set()

        for srs in srs_elements:
            srs = srs.text.strip().upper()
            if ' ' in srs:
                # handle multiple codes in one SRS tag (WMS 1.1.1 7.1.4.5.5)
                srs_codes.update(srs.split())
            else:
                srs_codes.add(srs)

        # unique srs-codes in either srs or parent_layer['srs']
        inherited_srs = parent_layer.get('srs', set()) if parent_layer else set()
        return srs_codes | inherited_srs

    def layer_bbox_srs(self, elem, parent_layer=None):
        bbox_srs = {}

        bbox_srs_elems = self.findall(elem, 'BoundingBox')
        if len(bbox_srs_elems) > 0:
            for bbox_srs_elem in bbox_srs_elems:
                srs = bbox_srs_elem.attrib['SRS']
                bbox = (
                    bbox_srs_elem.attrib['minx'],
                    bbox_srs_elem.attrib['miny'],
                    bbox_srs_elem.attrib['maxx'],
                    bbox_srs_elem.attrib['maxy']
                )
                bbox = [float(x) for x in bbox]
                bbox_srs[srs] = bbox
        elif parent_layer:
            bbox_srs = parent_layer['bbox_srs']

        return bbox_srs


class WMS130Capabilities(WMSCapabilities):
    version = '1.3.0'
    _default_namespace = 'http://www.opengis.net/wms'
    _ns = {
        'sld': "http://www.opengis.net/sld",
        'xlink': "http://www.w3.org/1999/xlink",
    }

    def layer_llbbox(self, elem, parent_layer):
        llbbox_elem = self.find(elem, 'EX_GeographicBoundingBox')
        llbbox = None
        if llbbox_elem is not None:
            llbbox = (
                self.find(llbbox_elem, 'westBoundLongitude').text,
                self.find(llbbox_elem, 'southBoundLatitude').text,
                self.find(llbbox_elem, 'eastBoundLongitude').text,
                self.find(llbbox_elem, 'northBoundLatitude').text
            )
            llbbox = [float(x) for x in llbbox]
        elif parent_layer and 'llbbox' in parent_layer:
            llbbox = parent_layer['llbbox']

        return llbbox

    def layer_srs(self, elem, parent_layer=None):
        srs_elements = self.findall(elem, 'CRS')
        srs_codes = set([srs.text.strip().upper() for srs in srs_elements])
        # unique srs-codes in either srs or parent_layer['srs']
        inherited_srs = parent_layer.get('srs', set()) if parent_layer else set()
        return srs_codes | inherited_srs

    def layer_bbox_srs(self, elem, parent_layer=None):
        bbox_srs = {}

        bbox_srs_elems = self.findall(elem, 'BoundingBox')
        if len(bbox_srs_elems) > 0:
            for bbox_srs_elem in bbox_srs_elems:
                srs = bbox_srs_elem.attrib['CRS']
                bbox = (
                    bbox_srs_elem.attrib['minx'],
                    bbox_srs_elem.attrib['miny'],
                    bbox_srs_elem.attrib['maxx'],
                    bbox_srs_elem.attrib['maxy']
                )
                bbox = [float(x) for x in bbox]
                bbox = switch_bbox_epsg_axis_order(bbox, srs)
                bbox_srs[srs] = bbox
        elif parent_layer:
            bbox_srs = parent_layer['bbox_srs']

        return bbox_srs

def yaml_sources(cap):
    sources = {}
    for layer in cap.layers():
        layer_name = layer['name'] + '_wms'
        req = dict(url='http://example', layers=layer['name'])
        if not layer['opaque']:
            req['transparent'] = True


        sources[layer_name] = dict(
            type='wms',
            req=req
        )

    import yaml
    print(yaml.dump(dict(sources=sources), default_flow_style=False))


def parse_capabilities(fileobj):
    if isinstance(fileobj, string_type):
        fileobj = open(fileobj, 'rb')
    tree = etree.parse(fileobj)
    root_tag = tree.getroot().tag
    if root_tag == 'WMT_MS_Capabilities':
        return WMS111Capabilities(tree)
    elif root_tag == '{http://www.opengis.net/wms}WMS_Capabilities':
        return WMS130Capabilities(tree)
    else:
        raise ValueError('unknown start tag in capabilities: ' + root_tag)

if __name__ == '__main__':
    import sys
    cap = parse_capabilities(sys.argv[1])
    yaml_sources(cap)
