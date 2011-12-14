import httplib2
import json
import threading

from cStringIO import StringIO

from mapproxy.image import ImageSource
from mapproxy.cache.base import (
    TileCacheBase, FileBasedLocking,
    tile_buffer, CacheBackendError,)
from mapproxy.source import SourceError
from mapproxy.util.times import parse_httpdate

class UnexpectedResponse(CacheBackendError):
    pass

class CouchDBCache(TileCacheBase, FileBasedLocking):
    def __init__(self, url, db_name, lock_dir,
        file_ext, tile_grid, store_document=False,
        tile_path_template=None):
        self.lock_cache_id = url + db_name
        self.lock_dir = lock_dir
        self.lock_timeout = 60
        self.file_ext = file_ext
        self.tile_grid = tile_grid
        self.store_document = store_document
        self.couch_url = '%s/%s' % (url.rstrip('/'), db_name)
        self.init_db()
        self.tile_path_template = tile_path_template
        self._h_cache = threading.local()

    def init_db(self):
        h = httplib2.Http()
        h.request(self.couch_url, 'PUT')
    
    @property
    def h(self):
        """
        Context local HTTP client
        """
        if not hasattr(self._h_cache, 'h'):
            self._h_cache.h = httplib2.Http()
        return self._h_cache.h
    
    def tile_url(self, coord):
        return self.document_url(coord) + '/tile'
        
    def document_url(self, coord):
        x, y, z = coord
        matrix_set = self.tile_grid.name
        couch_url = self.couch_url
        if self.tile_path_template:
            return self.tile_path_template % locals()
        else:
            return '%(couch_url)s/%(matrix_set)s-%(z)d-%(x)d-%(y)d' % locals()
    
    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        url = self.tile_url(tile.coord)
        resp, content = self.h.request(url, 'GET')
        if resp.status == 200:
            tile.source = ImageSource(StringIO(content))
            return True
        if resp.status == 404:
            return False
        raise SourceError('%r: %r' % (resp, content))
    
    def tile_document(self, tile):
        tile_bbox = self.tile_grid.tile_bbox(tile.coord)
        centroid = (
            tile_bbox[0] + (tile_bbox[2]-tile_bbox[0])/2,
            tile_bbox[1] + (tile_bbox[3]-tile_bbox[1])/2
        )
        x, y, z = tile.coord
        return {
            'centroid': centroid,
            'tile_row': x,
            'tile_column': y,
            'zoom_level': z,
        }
    
    def _store_tile_document(self, tile):
        tile_document = self.tile_document(tile)
        url = self.document_url(tile.coord)
        content_type = 'application/json'
        
        body = json.dumps(tile_document)
        
        resp, content = self.h.request(url, 'PUT',
            headers={'Content-type': content_type},
            body=body)
        
        if resp.status == 409:
            resp, content = self.h.request(url, 'HEAD')
            rev_id = resp['etag'].strip('"')
            tile_document['_rev'] = rev_id
            body = json.dumps(tile_document)
            resp, content = self.h.request(url, 'PUT',
                headers={'Content-type': content_type},
                body=body)
        elif resp.status != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status, content))
        
        return resp['etag'].strip('"')
    
    def _store_tile(self, url, data, content_type, rev_id=None):
        if rev_id:
            url += '?rev=' + rev_id
        resp, content = self.h.request(url, 'PUT',
            headers={'Content-type': 'image/' + self.file_ext},
            body=data)
        if resp.status == 409 and not rev_id:
            resp, content = self.h.request(url, 'HEAD')
            rev_id = resp['etag']
            url += '?rev=' + rev_id.strip('"')
            resp, content = self.h.request(url, 'PUT',
                headers={'Content-type': 'image/' + self.file_ext},
                body=data)
        elif resp.status != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status, content))
        
        return resp['etag'].strip('"')
    
    def store_tile(self, tile):
        if tile.stored:
            return True
            
        with tile_buffer(tile) as buf:
            url = self.tile_url(tile.coord)
            data = buf.read()
            
            rev_id = None
            if self.store_document:
                rev_id = self._store_tile_document(tile)
            self._store_tile(url, data, 'image/' + self.file_ext, rev_id=rev_id)
            return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        url = self.tile_url(tile.coord)
        resp, content = self.h.request(url, 'GET')
        if resp.status == 200:
            tile.source = ImageSource(StringIO(content))
            return True
        return False
    
    def remove_tile(self, tile):
        if tile.coord is None:
            return True
        url = self.tile_url(tile.coord)
        resp, content = self.h.request(url, 'HEAD')
        rev_id = resp['etag']
        url += '?rev=' + rev_id.strip('"')
        resp, content = self.h.request(url, 'DELETE')
        if resp.status == 200:
            return True
        return False
        
