import hashlib
import sys
try:
    from cStringIO import StringIO
except ImportError:
    from io import BytesIO as StringIO
from mapproxy.cache.base import TileCacheBase, tile_buffer, CacheBackendError
from mapproxy.image import ImageSource

try:
    from cassandra.cluster import Cluster
    cassandra_driver = True
except ImportError:
    cassandra_driver = None

import logging
log = logging.getLogger(__name__)


class UnexpectedResponse(CacheBackendError):
    pass


class CassandraCache(TileCacheBase):
    def __init__(self, nodes, port, keyspace, tablename, lock_dir):
        if not cassandra_driver:
            raise ImportError("Cassandra backend requires 'cassandra-driver' package.")
        self.nodes = nodes
        self.port = int(port)
        self.keyspace = keyspace
        self.tablename = tablename
        self.lock_dir = lock_dir
        self.lock_timeout = 60
        self.lock_cache_id = 'cassandra-' + hashlib.md5(keyspace.encode('utf-8') + tablename.encode('utf-8')).hexdigest()
        self.session = None

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        try:
            key = _tile_key(tile.coord)
            if not self.session:
                self._open_session()
            returned_key = self.session.execute(self.is_cached_stmt, [key])[0]
            if returned_key:
                return True
            else:
                return False
        except:
            return False

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        key = _tile_key(tile.coord)
        if not self.session:
            self._open_session()
        try:
            content = self.session.execute(self.get_tile_stmt, [key])[0]
            if content:
                tile.source = ImageSource(StringIO(content[0]))
                if with_metadata:
                    created = content[1]
                    if created:
                        tile.timestamp = created / 1000
                    length = content[2]
                    if length:
                        tile.size = length
                return True
            else:
                return False
        except:
            log.warn("Unable to load tile %s" % key)
            return False

    def load_tile_metadata(self, tile):
        if tile.timestamp:
            return
        self.load_tile(tile, with_metadata=True)
        return True

    def store_tile(self, tile):
        if tile.stored:
            return True
        key = _tile_key(tile.coord)
        with tile_buffer(tile) as buf:
            data = buf.read()
        size = tile.size
        if tile.timestamp:
            timestamp = int(tile.timestamp * 1000)
        else:
            timestamp = None
        if not self.session:
            self._open_session()
        if self.is_cached(tile):
            self.session.execute(self.update_tile_stmt, [data, timestamp, size, key])
        else:
            self.session.execute(self.insert_tile_stmt, [key, data, timestamp, size])
        return True

    def remove_tile(self, tile):
        if tile.source or tile.coord is None:
            return True
        if not self.session:
            self._open_session()
        key = _tile_key(tile.coord)
        self.session.execute(self.delete_tile_stmt, [key])
        return True

    def _open_session(self):
        serverlist = []
        for n in self.nodes:
            serverlist.append(n['host'])
        cluster = Cluster(serverlist, port=self.port)
        self.session = cluster.connect(self.keyspace)
        self.is_cached_stmt = self.session.prepare("SELECT key from %s WHERE key=?" % self.tablename)
        self.get_tile_stmt = self.session.prepare("SELECT img, created, length from %s where key=?" % self.tablename)
        self.delete_tile_stmt = self.session.prepare("DELETE FROM %s where key=?" % self.tablename)
        self.insert_tile_stmt = self.session.prepare("INSERT INTO %s (key, img, created, length) values (?, ?, ?, ?)" % self.tablename)
        self.update_tile_stmt = self.session.prepare("UPDATE %s SET img=?, created=?, length=? where key=?" % self.tablename)




def _tile_key(coord):
    """
    >>> _tile_key([2, 2, 2])
    '2_2_2'
    >>> _tile_key([1285, 3976, 12])
    '1285_3976_12'
    """
    x, y, z = coord
    return "%(x)s_%(y)s_%(z)s" % locals()
