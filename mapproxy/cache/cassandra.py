import hashlib
from cStringIO import StringIO
from mapproxy.cache.base import TileCacheBase, FileBasedLocking, tile_buffer
from mapproxy.image import ImageSource

try:
    import pycassa
    from pycassa.cassandra.ttypes import NotFoundException
except ImportError:
    pycassa = None

__author__ = 'meier_ul'


class CassandraCache(TileCacheBase, FileBasedLocking):
    def __init__(self, nodes, keyspace, column_family, lock_dir):
        if pycassa is None:
            raise ImportError("Cassandra backend requires 'pycassa' package.")
        self.nodes = nodes
        self.keyspace = keyspace
        self.column_family = column_family
        self.lock_dir = lock_dir
        self.lock_cache_id = 'cassandra-' + hashlib.md5(keyspace + column_family).hexdigest()
        self.cf = None

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        try:
            key = self._tile_key(tile.coord)
            self.cf.get(key)
        except NotFoundException:
            return False

    def lock(self, tile):
        pass

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        key = self._tile_key(tile.coord)
        if not self.cf:
            self._open_cf()
        content = self.cf.get(key)
        if content:
            tile.source = ImageSource(StringIO(content['img']))
            if with_metadata:
                tile.timestamp = content['created']
                tile.size = content['length']
            return True
        else:
            return False

    def load_tile_metadata(self, tile):
        if tile.timestamp:
            return
        self.load_tile(tile, with_metadata=True)
        return True

    def store_tile(self, tile):
        if tile.stored:
            return True
        size = tile.size
        timestamp = tile.timestamp
        key = self._tile_key(tile.coord)
        with tile_buffer(tile) as buf:
            data = buf.read()
        content = {key: {'created': timestamp, 'img': data, 'eins': 1, 'length': size}}
        if not self.cf:
            self._open_cf()
        self.cf.insert(content)
        return True

    def remove_tile(self, tile):
        if tile.source or tile.coord is None:
            return True
        if not self.cf:
            self._open_cf()
        key = self._tile_key(tile.coord)
        self.cf.remove(key)
        return True

    def _open_cf(self):
        pool = pycassa.ConnectionPool(keyspace=self.keyspace, server_list=self.nodes)
        cf = pycassa.ColumnFamily(pool, self.column_family)
        cf.column_validators = {'created': pycassa.types.DateType(),
                                'eins': pycassa.types.IntegerType(),  # legacy ... ;-)
                                'length': pycassa.types.IntegerType()}
        self.cf = cf

    @staticmethod
    def _tile_key(coord):
        x, y, z = coord
        return "%(x)s_%(y)s_%(z)s" % locals()