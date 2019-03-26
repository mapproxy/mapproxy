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

from __future__ import absolute_import

import sys
import time
import queue
import random
import threading
import multiprocessing

from mapproxy.grid import tile_grid
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, MapLayer
from mapproxy.source import  SourceError
from mapproxy.client.log import log_request
from mapproxy.util.py import reraise_exception
from mapproxy.util.async_ import run_non_blocking
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
                 res_range=None, lock=None, reuse_map_objects=False, scale_factor=None,
                 concurrent_tile_creators=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.mapfile = mapfile
        self.coverage = coverage
        self.res_range = res_range
        self.layers = set(layers) if layers else None
        self.scale_factor = scale_factor
        self.lock = lock
        # global objects to support multiprocessing
        global _map_objs
        _map_objs = {}
        global _last_activity
        _last_activity = time.time()
        self._cache_map_obj = reuse_map_objects
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        # pre-created mapfiles for higher reactivity
        global _last_mapfile
        _last_mapfile = None
        # pre-create more maps than the typical number of threads to allow for fast start
        global _map_objs_precreated
        if self._cache_map_obj:
            _precreate_count = 1
        else:
            _precreate_count = (2 * concurrent_tile_creators if concurrent_tile_creators else 4) # 4 is the default for async_.ThreadPool
        _map_objs_precreated = queue.Queue(_precreate_count)
        self.map_obj_pre_creating_thread = threading.Thread(target=self._precreate_maps)
        self.map_obj_pre_creating_thread.daemon = True
        self.map_obj_pre_creating_thread.start()

    def _idle(self):
        return time.time() > _last_activity + 30

    def _restart_idle_timer(self):
        global _last_activity
        _last_activity = time.time()

    def _precreate_maps(self):
        while True:
            mapfile = _last_mapfile
            if mapfile is None or _map_objs_precreated.full():
                time.sleep(60 * random.random()) # randomized wait to avoid multiprocessing issues
                continue
            if not self._idle():
                time.sleep(10 * random.random())
                continue
            _map_objs_precreated.put((mapfile, self._create_map_obj(mapfile)))
            # prefer creating currently needed maps to filling the cache
            time.sleep(5 + (10 * random.random()))

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

    def _create_map_obj(self, mapfile):
        m = mapnik.Map(0, 0)
        mapnik.load_map(m, str(mapfile))
        global _last_mapfile
        _last_mapfile = mapfile
        return m

    def _get_map_obj(self, mapfile):
        while not _map_objs_precreated.empty():
            try:
                mf, m = _map_objs_precreated.get()
            except queue.Empty:
                break
            if mf == mapfile:
                return m
        return self._create_map_obj(mapfile)

    def map_obj(self, mapfile):
        # avoid concurrent cache filling
        self._restart_idle_timer()
        # cache loaded map objects
        # only works when a single proc/thread accesses the map
        # (forking the render process doesn't work because of open database
        #  file handles that gets passed to the child)
        # segment the cache by process and thread to avoid interference
        if self._cache_map_obj:
            cachekey = None # renderd guarantees that there are no concurrency issues
        else:
            thread_id = threading.current_thread().ident
            process_id = multiprocessing.current_process()._identity
            cachekey = (process_id, thread_id, mapfile)
        if cachekey not in _map_objs:
            _map_objs[cachekey] = self._get_map_obj(mapfile)

        # clean up no longer used cached maps
        process_cache_keys = [k for k in _map_objs.keys()
                              if k[0] == process_id]
        if len(process_cache_keys) > (5 + threading.active_count()):
            active_thread_ids = set(i.ident for i in threading.enumerate())
            for k in process_cache_keys:
                if not k[1] in active_thread_ids and k in _map_objs:
                    try:
                        m = _map_objs[k]
                        del _map_objs[k]
                    except KeyError:
                        continue
                    m.remove_all() # cleanup
                    mapnik.clear_cache()

        self._restart_idle_timer()
        return _map_objs[cachekey]

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
            image_opts=ImageOptions(format=query.format))
