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

import re

from mapproxy.response import Response
from mapproxy.exception import RequestError, PlainExceptionHandler
from mapproxy.service.base import Server
from mapproxy.request.tile import TileRequest
from mapproxy.srs import SRS

class KMLRequest(TileRequest):
    """
    Class for TMS-like KML requests.
    """
    request_handler_name = 'map'
    req_prefix = '/kml'
    tile_req_re = re.compile(r'''^(?P<begin>/kml)/
            (?P<layer>[^/]+)/
            ((?P<layer_spec>[^/]+)/)?
            (?P<z>-?\d+)/
            (?P<x>-?\d+)/
            (?P<y>-?\d+)\.(?P<format>\w+)''', re.VERBOSE)
    
    def __init__(self, request):
        TileRequest.__init__(self, request)
        if self.format == 'kml':
            self.request_handler_name = 'kml'
    
    @property
    def exception_handler(self):
        return PlainExceptionHandler()

def kml_request(req):
    return KMLRequest(req)

class KMLServer(Server):
    """
    OGC KML 2.2 Server 
    """
    names = ('kml',)
    request_parser = staticmethod(kml_request)
    request_methods = ('map', 'kml')

    def __init__(self, layers, md, max_tile_age=None):
        Server.__init__(self)
        self.layers = layers
        self.md = md
        self.max_tile_age = max_tile_age
    
    def map(self, map_request):
        """
        :return: the requested tile
        """
        layer = self.layer(map_request)
        self.authorize_tile_layer(layer.name, map_request.http.environ)
        tile = layer.render(map_request)
        resp = Response(tile.as_buffer(),
                        content_type='image/' + map_request.format)
        resp.cache_headers(tile.timestamp, etag_data=(tile.timestamp, tile.size),
                           max_age=self.max_tile_age)
        resp.make_conditional(map_request.http)
        return resp
    
    def authorize_tile_layer(self, layer_name, env):
        if 'mapproxy.authorize' in env:
            result = env['mapproxy.authorize']('kml', [layer_name], environ=env)
            if result['authorized'] == 'unauthenticated':
                raise RequestError('unauthorized', status=401)
            if result['authorized'] == 'full':
                return
            if result['authorized'] == 'partial':
                if result['layers'].get(layer_name, {}).get('tile', False) == True:
                    return
            raise RequestError('forbidden', status=403)
    
    def layer(self, tile_request):
        if tile_request.layer in self.layers:
            return self.layers[tile_request.layer]
        if tile_request.layer + '_EPSG4326' in self.layers:
            return self.layers[tile_request.layer + '_EPSG4326']
        if tile_request.layer + '_EPSG900913' in self.layers:
            return self.layers[tile_request.layer + '_EPSG900913']
        raise RequestError('unknown layer: ' + tile_request.layer, request=tile_request)

    def kml(self, map_request):
        """
        :return: the rendered KML response
        """
        layer = self.layer(map_request)
        self.authorize_tile_layer(layer.name, map_request.http.environ)
        
        tile_coord = map_request.tile
        
        initial_level = False
        if tile_coord[2] == 0:
            initial_level = True
        
        bbox = self._tile_wgs_bbox(tile_coord, layer.grid, limit=True)
        if bbox is None:
            raise RequestError('The requested tile is outside the bounding box '
                               'of the tile map.', request=map_request)
        tile = SubTile(tile_coord, bbox)
        
        subtiles = self._get_subtiles(tile_coord, layer)
        tile_size = layer.grid.tile_size[0]
        url = map_request.http.script_url.rstrip('/')
        result = KMLRenderer().render(tile=tile, subtiles=subtiles, layer=layer,
            url=url, name=map_request.layer, format=layer.format, name_path=layer.md['name_path'],
            initial_level=initial_level, tile_size=tile_size)
        resp = Response(result, content_type='application/vnd.google-earth.kml+xml')
        resp.cache_headers(etag_data=(result,), max_age=self.max_tile_age)
        resp.make_conditional(map_request.http)
        return resp

    def _get_subtiles(self, tile, layer):
        """
        Create four `SubTile` for the next level of `tile`.
        """
        bbox = self._tile_bbox(tile, layer.grid, limit=True)
        level = layer.grid.internal_tile_coord((tile[0], tile[1], tile[2]+1), use_profiles=False)[2]
        bbox_, tile_grid_, tiles = layer.grid.get_affected_level_tiles(bbox, level)
        subtiles = []
        for coord in tiles:
            if coord is None: continue
            sub_bbox = layer.grid.tile_bbox(coord)
            if sub_bbox is not None:
                # only add subtiles where the lower left corner is in the bbox
                # to prevent subtiles to apear in multiple KML docs
                if sub_bbox[0] >= bbox[0] and sub_bbox[1] >= bbox[1]:
                    sub_bbox_wgs = self._tile_bbox_to_wgs(sub_bbox, layer.grid)
                    coord = layer.grid.external_tile_coord(coord, use_profiles=False)
                    subtiles.append(SubTile(coord, sub_bbox_wgs))

        return subtiles

    def _tile_bbox(self, tile_coord, grid, limit=False):
        tile_coord = grid.internal_tile_coord(tile_coord, use_profiles=False)
        if tile_coord is None:
            return None
        return grid.tile_bbox(tile_coord, limit=limit)
    
    def _tile_wgs_bbox(self, tile_coord, grid, limit=False):
        src_bbox = self._tile_bbox(tile_coord, grid, limit=limit)
        if src_bbox is None:
            return None
        return self._tile_bbox_to_wgs(src_bbox, grid)
        
    def _tile_bbox_to_wgs(self, src_bbox, grid):
        bbox = grid.srs.transform_bbox_to(SRS(4326), src_bbox, with_points=4)
        if grid.srs == SRS(900913):
            bbox = list(bbox)
            if abs(src_bbox[1] -  -20037508.342789244) < 0.1:
                bbox[1] = -90.0
            if abs(src_bbox[3] -  20037508.342789244) < 0.1:
                bbox[3] = 90.0
        return bbox
    
    def check_map_request(self, map_request):
        if map_request.layer not in self.layers:
            raise RequestError('unknown layer: ' + map_request.layer, request=map_request)


class SubTile(object):
    """
    Contains the ``bbox`` and ``coord`` of a sub tile.
    """
    def __init__(self, coord, bbox):
        self.coord = coord
        self.bbox = bbox

class KMLRenderer(object):
    header = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>%(layer_name)s</name>
    <Region>
      <LatLonAltBox>
        <north>%(north)f</north><south>%(south)f</south>
        <east>%(east)f</east><west>%(west)f</west>
      </LatLonAltBox>
    </Region>
    """
  
    network_link = """<NetworkLink>
      <name>%(layer_name)s - %(coord)s</name>
      <Region>
        <LatLonAltBox>
          <north>%(north)f</north><south>%(south)f</south>
          <east>%(east)f</east><west>%(west)f</west>
        </LatLonAltBox>
        <Lod>
          <minLodPixels>%(min_lod)d</minLodPixels>
          <maxLodPixels>-1</maxLodPixels>
        </Lod>
      </Region>
      <Link>
        <href>%(href)s</href>
        <viewRefreshMode>onRegion</viewRefreshMode>
        <viewFormat/>
      </Link>
    </NetworkLink>
    """
    ground_overlay = """<GroundOverlay>
      <name>%(coord)s</name>
      <Region>
        <LatLonAltBox>
          <north>%(north)f</north><south>%(south)f</south>
          <east>%(east)f</east><west>%(west)f</west>
        </LatLonAltBox>
        <Lod>
          <minLodPixels>%(min_lod)d</minLodPixels>
          <maxLodPixels>%(max_lod)d</maxLodPixels>
          <minFadeExtent>8</minFadeExtent>
          <maxFadeExtent>8</maxFadeExtent>
        </Lod>
      </Region>
      <drawOrder>%(level)d</drawOrder>
      <Icon>
        <href>%(href)s</href>
      </Icon>
      <LatLonBox>
        <north>%(north)f</north><south>%(south)f</south>
        <east>%(east)f</east><west>%(west)f</west>
      </LatLonBox>
    </GroundOverlay>
    """
    footer = """</Document>
</kml>
"""
    def render(self, tile, subtiles, layer, url, name, name_path, format, initial_level, tile_size):
        response = []
        response.append(self.header % dict(east=tile.bbox[2], south=tile.bbox[1],
            west=tile.bbox[0], north=tile.bbox[3], layer_name=name))
        
        name_path = '/'.join(name_path)
        for subtile in subtiles:
            kml_href = '%s/kml/%s/%d/%d/%d.kml' % (url, name_path,
                subtile.coord[2], subtile.coord[0], subtile.coord[1])
            response.append(self.network_link % dict(east=subtile.bbox[2], south=subtile.bbox[1],
                west=subtile.bbox[0], north=subtile.bbox[3], min_lod=tile_size/2, href=kml_href,
                layer_name=name, coord=subtile.coord))
        
        for subtile in subtiles:
            tile_href = '%s/kml/%s/%d/%d/%d.%s' % ( url, name_path,
                subtile.coord[2], subtile.coord[0], subtile.coord[1], layer.format)
            response.append(self.ground_overlay % dict(east=subtile.bbox[2], south=subtile.bbox[1],
                west=subtile.bbox[0], north=subtile.bbox[3], coord=subtile.coord, 
                min_lod=tile_size/2, max_lod=tile_size*3, href=tile_href, level=subtile.coord[2]))
        response.append(self.footer)
        return ''.join(response)