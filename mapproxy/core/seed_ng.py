from __future__ import with_statement
import yaml
import multiprocessing
from mapproxy.core.srs import SRS
from mapproxy.core import seed
from mapproxy.core.grid import bbox_intersects
from mapproxy.core.cache import TileSourceError
from mapproxy.core.utils import cleanup_directory

"""
>>> g = grid.TileGrid()
>>> seed_bbox = (-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428)
>>> seed_level = 2, 4
>>> seed(g, seed_bbox, seed_level)

"""

def exp_backoff(func, max_repeat=10, start_backoff_sec=2, 
        exceptions=(Exception,)):
    n = 0
    while True:
        try:
            result = func()
        except exceptions, ex:
            if (n+1) >= max_repeat:
                raise
            wait_for = start_backoff_sec * 2**n
            print >>sys.stderr, ("An error occured. Retry in %d seconds: %r" % 
                (wait_for, ex))
            time.sleep(wait_for)
            n += 1
        else:
            return result

class SeedPool(object):
    def __init__(self, cache, size=4):
        self.tiles_queue = multiprocessing.Queue(16)
        self.cache = cache
        self.procs = []
        for _ in xrange(size):
            worker = SeedWorker(cache, self.tiles_queue)
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
    def __init__(self, cache, tiles_queue):
        multiprocessing.Process.__init__(self)
        self.cache = cache
        self.tiles_queue = tiles_queue
    def run(self):
        while True:
            seed_id, tiles = self.tiles_queue.get()
            if tiles is None:
                return
            print seed_id
            load_tiles = lambda: self.cache.cache_mgr.load_tile_coords(tiles)
            exp_backoff(load_tiles, exceptions=(TileSourceError, IOError))

class TileSeeder(object):
    def __init__(self, vlayer, remove_before, progress_meter, dry_run=False):
        self.remove_before = remove_before
        self.progress = progress_meter
        self.dry_run = dry_run
        self.caches = []
        if hasattr(vlayer, 'layers'): # MultiLayer
            vlayer = vlayer.layers
        else:
            vlayer = [vlayer]
        for layer in vlayer:
            if hasattr(layer, 'sources'): # VLayer
                self.caches.extend([source.cache for source in layer.sources
                                    if hasattr(source, 'cache')])
            else:
                self.caches.append(layer.cache)
    
    def seed_location(self, bbox, level, srs, cache_srs):
        for cache in self.caches:
            if not cache_srs or cache.grid.srs in cache_srs:
                self._seed_location(cache, bbox, level=level, srs=srs)
    
    def _seed_location(self, cache, bbox, level, srs):
        if cache.grid.srs != srs:
            bbox = srs.transform_bbox_to(cache.grid.srs, bbox)
        print cache
        if self.remove_before:
            cache.cache_mgr.expire_timestamp = lambda tile: self.remove_before
        
        seed_pool = SeedPool(cache)
        
        grid = cache.grid
        status = list('.oO0')
        def _seed(cur_bbox, level, max_level, id=''):
            bbox, tiles, subtiles = grid.get_affected_level_tiles(cur_bbox, level)
            subtiles = list(subtiles)
            if level < max_level:
                for i, subtile in enumerate(subtiles):
                    if subtile is None: continue
                    sub_bbox = grid.tile_bbox(subtile)
                    if bbox_intersects(sub_bbox, bbox):
                        seed_id = id + (status[i] if i <=3 else 'x')
                        _seed(sub_bbox, level+1, max_level, seed_id)
            # print id #, level, tiles, cur_bbox
            seed_pool.seed(id, subtiles)
        _seed(bbox, level[0], level[1])
        
        seed_pool.stop()
    
    def _seed_tiles(self, cache, tiles):
        if not self.dry_run:
            cache.cache_mgr.load_tile_coords(tiles)
       
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
        seeder = TileSeeder(server.layers[layer], remove_before=remove_before,
                            progress_meter=progress_meter(), dry_run=dry_run)
        for view in options['views']:
            view_conf = seed_conf['views'][view]
            srs = view_conf.get('bbox_srs', None)
            bbox = view_conf['bbox']
            cache_srs = view_conf.get('srs', None)
            if cache_srs is not None:
                cache_srs = [SRS(s) for s in cache_srs]
            if srs is not None:
                srs = SRS(srs)
            level = view_conf.get('level', None)
            seeder.seed_location(bbox, level=level, srs=srs, 
                                     cache_srs=cache_srs)
        
        if remove_before:
            seeder.cleanup()

import signal

def load_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import load_base_config
        load_base_config(conf_file)

def set_service_config(conf_file=None):
    if conf_file is not None:
        from mapproxy.core.config import base_config
        base_config().services_conf = conf_file

def stop_processing(_signal, _frame):
    print "Stopping..."
    TileSeeder.stop_all()
    return 0

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
    parser.add_option("-r", "--secure_rebuild",
                      action="store_true", dest="secure_rebuild", default=False,
                      help="do not rebuild tiles inplace. rebuild each level change"
                           " the level cache afterwards.")
    parser.add_option("-n", "--dry-run",
                      action="store_true", dest="dry_run", default=False,
                      help="do not seed, just print output")    
    
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.error('missing seed_conf file as last argument')
    
    load_config(options.conf_file)
    set_service_config(options.services_file)
    
    #signal.signal(signal.SIGINT, stop_processing)
    
    seed_from_yaml_conf(args[0], verbose=options.verbose,
                        dry_run=options.dry_run)

if __name__ == '__main__':
    main()