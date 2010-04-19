from __future__ import with_statement, division
import sys
import math
import time
import yaml
import datetime
import multiprocessing
from functools import partial

from mapproxy.core.srs import SRS
from mapproxy.core import seed
from mapproxy.core.grid import MetaGrid, bbox_intersects, bbox_contains
from mapproxy.core.cache import TileSourceError
from mapproxy.core.utils import cleanup_directory
from mapproxy.core.config import base_config, load_base_config


try:
    import shapely.wkt
    import shapely.prepared 
    import shapely.geometry
except ImportError:
    shapely_present = False
else:
    shapely_present = True


"""
>>> g = grid.TileGrid()
>>> seed_bbox = (-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428)
>>> seed_level = 2, 4
>>> seed(g, seed_bbox, seed_level)

"""

class SeedPool(object):
    def __init__(self, cache, size=2, dry_run=False):
        self.tiles_queue = multiprocessing.Queue(32)
        self.cache = cache
        self.dry_run = dry_run
        self.procs = []
        for _ in xrange(size):
            worker = SeedWorker(cache, self.tiles_queue, dry_run=dry_run)
            worker.start()
            self.procs.append(worker)
    
    def seed(self, seed_id, tiles):
        self.tiles_queue.put((seed_id, tiles))
    
    def stop(self):
        for _ in xrange(len(self.procs)):
            self.tiles_queue.put((None, None))
        
        for proc in self.procs:
            proc.join()
    
class SeedWorker(multiprocessing.Process):
    def __init__(self, cache, tiles_queue, dry_run=False):
        multiprocessing.Process.__init__(self)
        self.cache = cache
        self.tiles_queue = tiles_queue
        self.dry_run = dry_run
    def run(self):
        while True:
            seed_id, tiles = self.tiles_queue.get()
            if tiles is None:
                return
            print '[%s] %s\r' % (timestamp(), seed_id), #, tiles
            sys.stdout.flush()
            if not self.dry_run:
                load_tiles = lambda: self.cache.cache_mgr.load_tile_coords(tiles)
                exp_backoff(load_tiles, exceptions=(TileSourceError, IOError))

class TileSeeder(object):
    def __init__(self, caches, remove_before, progress_meter, dry_run=False):
        self.remove_before = remove_before
        self.progress = progress_meter
        self.dry_run = dry_run
        self.caches = caches
    
    def seed_location(self, bbox, level, srs, cache_srs, geom=None):
        for cache in self.caches:
            if not cache_srs or cache.grid.srs in cache_srs:
                self._seed_location(cache, bbox, level=level, srs=srs, geom=geom)
    
    def _seed_location(self, cache, bbox, level, srs, geom):
        if cache.grid.srs != srs:
            if geom is not None:
                geom = transform_geometry(srs, cache.grid.srs, geom)
                bbox = geom.bounds
            else:
                bbox = srs.transform_bbox_to(cache.grid.srs, bbox)
            
        start_level, max_level = level[0], level[1]
        
        if self.remove_before:
            cache.cache_mgr.expire_timestamp = lambda tile: self.remove_before
        
        seed_pool = SeedPool(cache, dry_run=self.dry_run)
        
        num_seed_levels = level[1] - level[0] + 1
        report_till_level = level[0] + int(num_seed_levels * 0.7)
        grid = MetaGrid(cache.grid, meta_size=base_config().cache.meta_size)
        
        # create intersects function
        # should return: 0 for no intersection, 1 for intersection,
        # -1 for full contains of the sub_bbox
        if geom is not None:
            prep_geom = shapely.prepared.prep(geom)
            def intersects(sub_bbox):
                bbox_poly = shapely.geometry.Polygon((
                    (sub_bbox[0], sub_bbox[1]),
                    (sub_bbox[2], sub_bbox[1]),
                    (sub_bbox[2], sub_bbox[3]),
                    (sub_bbox[0], sub_bbox[3]),
                    ))
                if prep_geom.contains(bbox_poly): return -1
                if prep_geom.intersects(bbox_poly): return 1
                return 0
        else:
            def intersects(sub_bbox):
                if bbox_contains(bbox, sub_bbox): return -1
                if bbox_intersects(bbox, sub_bbox): return 1
                return 0
        
        def _seed(cur_bbox, level, id='', full_intersect=False):
            """
            :param cur_bbox: the bbox to seed in this call
            :param level: the current seed level
            :param full_intersect: do not check for intersections with bbox if True
            """
            bbox_, tiles_, subtiles = grid.get_affected_level_tiles(cur_bbox, level)
            subtiles = list(subtiles)
            if level <= report_till_level:
                print '[%s] %2s %s full:%r' % (timestamp(), level, format_bbox(cur_bbox),
                                               full_intersect)
                sys.stdout.flush()
            if level < max_level:
                sub_seeds = []
                for subtile in subtiles:
                    if subtile is None: continue
                    sub_bbox = grid.meta_bbox(subtile)
                    intersection = -1 if full_intersect else intersects(sub_bbox)
                    if intersection:
                        sub_seeds.append((sub_bbox, intersection))
                
                if sub_seeds:
                    total_sub_seeds = len(sub_seeds)
                    for i, (sub_bbox, intersection) in enumerate(sub_seeds):
                        seed_id = id + status_symbol(i, total_sub_seeds)
                        full_intersect = True if intersection == -1 else False
                        _seed(sub_bbox, level+1, seed_id,
                              full_intersect=full_intersect)
            seed_pool.seed(id, subtiles)
        _seed(bbox, start_level)
        
        seed_pool.stop()
    
    def cleanup(self):
        for cache in self.caches:
            for i in range(cache.grid.levels):
                level_dir = cache.cache_mgr.cache.level_location(i)
                if self.dry_run:
                    def file_handler(filename):
                        self.progress.print_msg('removing ' + filename)
                else:
                    file_handler = None
                self.progress.print_msg('removing oldfiles in ' + level_dir)
                cleanup_directory(level_dir, self.remove_before,
                    file_handler=file_handler)
            
def timestamp():
    return datetime.datetime.now().strftime('%H:%M:%S')

def format_bbox(bbox):
    return ('(%.5f, %.5f, %.5f, %.5f)') % bbox

def status_symbol(i, total):
    """
    >>> status_symbol(0, 1)
    '0'
    >>> [status_symbol(i, 4) for i in range(5)]
    ['.', 'o', 'O', '0', 'X']
    >>> [status_symbol(i, 10) for i in range(11)]
    ['.', '.', 'o', 'o', 'o', 'O', 'O', '0', '0', '0', 'X']
    """
    symbols = list(' .oO0')
    i += 1
    if 0 < i > total:
        return 'X'
    else:
        return symbols[int(math.ceil(i/(total/4)))]

def seed_from_yaml_conf(conf_file, verbose=True, rebuild_inplace=True, dry_run=False):
    from mapproxy.core.conf_loader import load_services
    
    if hasattr(conf_file, 'read'):
        seed_conf = yaml.load(conf_file)
    else:
        with open(conf_file) as conf_file:
            seed_conf = yaml.load(conf_file)
    
    if verbose:
        progress_meter = seed.TileProgressMeter
    else:
        progress_meter = seed.NullProgressMeter
    
    services = load_services()
    if 'wms' in services:
        server  = services['wms']
    elif 'tms' in services:
        server  = services['tms']
    else:
        print 'no wms or tms server configured. add one to your proxy.yaml'
        return
    for layer, options in seed_conf['seeds'].iteritems():
        remove_before = seed.before_timestamp_from_options(options)
        caches = caches_from_layer(server.layers[layer])
        seeder = TileSeeder(caches, remove_before=remove_before,
                            progress_meter=progress_meter(), dry_run=dry_run)
        for view in options['views']:
            view_conf = seed_conf['views'][view]
            srs = view_conf.get('bbox_srs', None)
            bbox = view_conf['bbox']
            geom = None
            if isinstance(bbox, basestring):
                if not shapely_present:
                    print 'need shapely to support polygon seed areas'
                    return
                bbox, geom = load_geom(bbox)
            
            cache_srs = view_conf.get('srs', None)
            if cache_srs is not None:
                cache_srs = [SRS(s) for s in cache_srs]
            if srs is not None:
                srs = SRS(srs)
            level = view_conf.get('level', None)
            seeder.seed_location(bbox, level=level, srs=srs, 
                                     cache_srs=cache_srs, geom=geom)
        
        if remove_before:
            seeder.cleanup()


def caches_from_layer(layer):
    caches = []
    if hasattr(layer, 'layers'): # MultiLayer
        layers = layer.layers
    else:
        layers = [layer]
    for layer in layers:
        if hasattr(layer, 'sources'): # VLayer
            caches.extend([source.cache for source in layer.sources
                                if hasattr(source, 'cache')])
        else:
            caches.append(layer.cache)
    return caches

def load_geom(geom_file):
    polygons = []
    with open(geom_file) as f:
        for line in f:
            polygons.append(shapely.wkt.loads(line))
    
    mp = shapely.geometry.MultiPolygon(polygons)
    return mp.bounds, mp

def transform_geometry(from_srs, to_srs, geometry):
    transf = partial(transform_xy, from_srs, to_srs)
    
    if geometry.type == 'Polygon':
        return transform_polygon(transf, geometry)
    
    if geometry.type == 'MultiPolygon':
        return transform_multipolygon(transf, geometry)

def transform_polygon(transf, polygon):
    ext = transf(polygon.exterior.xy)
    ints = [transf(ring.xy) for ring in polygon.interiors]
    return shapely.geometry.Polygon(ext, ints)

def transform_multipolygon(transf, multipolygon):
    transformed_polygons = []
    for polygon in multipolygon:
        transformed_polygons.append(transform_polygon(transf, polygon))
    return shapely.geometry.MultiPolygon(transformed_polygons)


def transform_xy(from_srs, to_srs, xy):
    return list(from_srs.transform_to(to_srs, zip(*xy)))

import signal

def load_config(conf_file=None):
    if conf_file is not None:
        load_base_config(conf_file)

def set_service_config(conf_file=None):
    if conf_file is not None:
        base_config().services_conf = conf_file

def main():
    from optparse import OptionParser
    usage = "usage: %prog [options] seed_conf"
    parser = OptionParser(usage)
    parser.add_option("-q", "--quiet",
                      action="store_false", dest="verbose", default=True,
                      help="don't print status messages to stdout")
    parser.add_option("-f", "--proxy-conf",
                      dest="conf_file", default=None,
                      help="proxy configuration")
    parser.add_option("-s", "--services-conf",
                      dest="services_file", default=None,
                      help="services configuration")
    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do not seed, just print output")    
    
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error('missing seed_conf file as last argument')
    
    if not options.conf_file:
        parser.error('set proxy configuration with -f')
    
    load_config(options.conf_file)
    set_service_config(options.services_file)
    
    seed_from_yaml_conf(args[0], verbose=options.verbose,
                        dry_run=options.dry_run)

if __name__ == '__main__':
    main()