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

from __future__ import with_statement, absolute_import

import sys
import time
import threading

from mapproxy.grid import tile_grid
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, MapLayer
from mapproxy.source import  SourceError
from mapproxy.client.log import log_request
from mapproxy.util.py import reraise_exception
from mapproxy.util.async import run_non_blocking
from mapproxy.compat import BytesIO

try:
    import mapnik
    mapnik
except ImportError:
    try:
        # for 2.0 alpha/rcs and first 2.0 release
        import mapnik2 as mapnik
    except ImportError:
        mapnik = None

# fake 2.0 API for older versions
if mapnik and not hasattr(mapnik, 'Box2d'):
    mapnik.Box2d = mapnik.Envelope

import logging
log = logging.getLogger(__name__)

class MapnikSource(MapLayer):
    supports_meta_tiles = True
    def __init__(self, mapfile, layers=None, image_opts=None, coverage=None,
        res_range=None, lock=None, reuse_map_objects=False, scale_factor=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.mapfile = mapfile
        self.coverage = coverage
        self.res_range = res_range
        self.layers = set(layers) if layers else None
        self.scale_factor = scale_factor
        self.lock = lock
        self._map_objs = {}
        self._map_objs_lock = threading.Lock()
        self._cache_map_obj = reuse_map_objects
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()

    def get_map(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()

        try:
            resp = self.render(query)
        except RuntimeError as ex:
            log.error('could not render Mapnik map: %s', ex)
            reraise_exception(SourceError(ex.args[0]), sys.exc_info())
        resp.opacity = self.opacity
        return resp

    def render(self, query):
        mapfile = self.mapfile
        if '%(webmercator_level)' in mapfile:
            _bbox, level = tile_grid(3857).get_affected_bbox_and_level(
                query.bbox, query.size, req_srs=query.srs)
            mapfile = mapfile % {'webmercator_level': level}

        if self.lock:
            with self.lock():
                return self.render_mapfile(mapfile, query)
        else:
            return self.render_mapfile(mapfile, query)

    def map_obj(self, mapfile):
        if not self._cache_map_obj:
            m = mapnik.Map(0, 0)
            mapnik.load_map(m, str(mapfile))
            return m

        # cache loaded map objects
        # only works when a single proc/thread accesses this object
        # (forking the render process doesn't work because of open database
        #  file handles that gets passed to the child)
        if mapfile not in self._map_objs:
            with self._map_objs_lock:
                if mapfile not in self._map_objs:
                    m = mapnik.Map(0, 0)
                    mapnik.load_map(m, str(mapfile))
                    self._map_objs[mapfile] = m

        return self._map_objs[mapfile]

    def render_mapfile(self, mapfile, query):
        return run_non_blocking(self._render_mapfile, (mapfile, query))

    def _render_mapfile(self, mapfile, query):
        start_time = time.time()

        m = self.map_obj(mapfile)
        m.resize(query.size[0], query.size[1])
        m.srs = '+init=%s' % str(query.srs.srs_code.lower())
        envelope = mapnik.Box2d(*query.bbox)
        m.zoom_to_box(envelope)
        data = None

        try:
            if self.layers:
                i = 0
                for layer in m.layers[:]:
                    if layer.name != 'Unkown' and layer.name not in self.layers:
                        del m.layers[i]
                    else:
                        i += 1

            img = mapnik.Image(query.size[0], query.size[1])
            if self.scale_factor:
                mapnik.render(m, img, self.scale_factor)
            else:
                mapnik.render(m, img)
            data = img.tostring(str(query.format))
        finally:
            size = None
            if data:
                size = len(data)
            log_request('%s:%s:%s:%s' % (mapfile, query.bbox, query.srs.srs_code, query.size),
                status='200' if data else '500', size=size, method='API', duration=time.time()-start_time)

        return ImageSource(BytesIO(data), size=query.size,
            image_opts=ImageOptions(transparent=self.transparent, format=query.format))
