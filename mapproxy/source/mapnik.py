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

try:
    import queue
    Queue = queue.Queue
    Empty = queue.Empty
    Full = queue.Full
except ImportError: # in python2 it is called Queue
    import Queue
    Empty = Queue.Empty
    Full = Queue.Full
MAX_UNUSED_MAPS=10

# fake 2.0 API for older versions
if mapnik and not hasattr(mapnik, 'Box2d'):
    mapnik.Box2d = mapnik.Envelope

import logging
log = logging.getLogger(__name__)

class MapnikSource(MapLayer):
    supports_meta_tiles = True
    def __init__(self, mapfile, layers=None, image_opts=None, coverage=None,
                 res_range=None, lock=None, reuse_map_objects=False,
                 scale_factor=None, multithreaded=False):
        MapLayer.__init__(self, image_opts=image_opts)
        self.mapfile = mapfile
        self.coverage = coverage
        self.res_range = res_range
        self.layers = set(layers) if layers else None
        self.scale_factor = scale_factor
        self.lock = lock
        self.multithreaded = multithreaded
        self._cache_map_obj = reuse_map_objects
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        if multithreaded:
            # global objects allow caching over multiple instances within the same worker process
            global _map_objs # mapnik map objects by cachekey
            _map_objs = {}
            global _map_objs_lock
            _map_objs_lock = threading.Lock()
            global _map_objs_queues # queues of unused mapnik map objects by PID and mapfile
            _map_objs_queues = {}
        else:
            # instance variables guarantee separation of caches
            self._map_objs = {}
            self._map_objs_lock = threading.Lock()

    def _map_cache(self):
        """Get the cache for map objects.

        Uses an instance variable for containment when multithreaded
        operation is disabled.
        """
        if self.multithreaded:
            return _map_objs
        return self._map_objs
    def _map_cache_lock(self):
        """Get the cache-locks for map objects.

        Uses an instance variable for containment when multithreaded
        operation is disabled.
        """
        if self.multithreaded:
            return _map_objs_lock
        return self._map_objs_lock

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

    def _create_map_obj(self, mapfile, process_id):
        m = mapnik.Map(0, 0)
        mapnik.load_map(m, str(mapfile))
        m.map_obj_pid = process_id
        return m

    def _get_map_obj(self, mapfile):
        if not self.multithreaded:
            return self._create_map_obj(mapfile, None)

        process_id = multiprocessing.current_process()._identity
        queue_cachekey = (process_id, mapfile)
        if queue_cachekey in _map_objs_queues:
            try:
                m = _map_objs_queues[queue_cachekey].get_nowait()
                # check explicitly for the process ID to ensure that
                # map objects cannot move between processes
                if m.map_obj_pid == process_id:
                    return m
            except Empty:
                pass
        return self._create_map_obj(mapfile, process_id)

    def _put_unused_map_obj(self, mapfile, m):
        process_id = multiprocessing.current_process()._identity
        queue_cachekey = (process_id, mapfile)
        if not queue_cachekey in _map_objs_queues:
            _map_objs_queues[queue_cachekey] = Queue(MAX_UNUSED_MAPS)
        try:
            _map_objs_queues[queue_cachekey].put_nowait(m)
        except Full:
            # cleanup the data and drop the map, so it can be garbage collected
            m.remove_all()
            mapnik.clear_cache()

    def _get_cachekey(self, mapfile):
        if not self.multithreaded or self._cache_map_obj:
            # all MapnikSources with the same mapfile share the same Mapnik Map.
            return (None, None, mapfile)
        thread_id = threading.current_thread().ident
        process_id = multiprocessing.current_process()._identity
        return (process_id, thread_id, mapfile)

    def _cleanup_unused_cached_maps(self, mapfile):
        if not self.multithreaded:
            return
        # clean up no longer used cached maps
        process_id = multiprocessing.current_process()._identity
        process_cache_keys = [k for k in self._map_cache().keys()
                              if k[0] == process_id]
        # To avoid time-consuming cleanup whenever one thread in the
        # threadpool finishes, allow ignoring up to 5 dead mapnik
        # instances.  (5 is empirical)
        if len(process_cache_keys) > (5 + threading.active_count()):
            active_thread_ids = set(i.ident for i in threading.enumerate())
            for k in process_cache_keys:
                with self._map_cache_lock():
                    if not k[1] in active_thread_ids and k in self._map_cache():
                        try:
                            m = self._map_cache()[k]
                            del self._map_cache()[k]
                            # put the map into the queue of unused
                            # maps so it can be re-used from another
                            # thread.
                            self._put_unused_map_obj(mapfile, m)
                        except KeyError:
                            continue

    def map_obj(self, mapfile):
        # cache loaded map objects
        # only works when a single proc/thread accesses the map
        # (forking the render process doesn't work because of open database
        #  file handles that gets passed to the child)
        # segment the cache by process and thread to avoid interference
        cachekey = self._get_cachekey(mapfile)
        with self._map_cache_lock():
            if cachekey not in self._map_cache():
                self._map_cache()[cachekey] = self._get_map_obj(mapfile)
            mapnik_map = self._map_cache()[cachekey]

        self._cleanup_unused_cached_maps(mapfile)

        return mapnik_map

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
                    if layer.name != 'Unknown' and layer.name not in self.layers:
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
