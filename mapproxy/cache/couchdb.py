import requests
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
        self.couch_url = '%s/%s' % (url.rstrip('/'), db_name.lower())
        self.init_db()
        self.tile_path_template = tile_path_template

    def init_db(self):
        requests.put(self.couch_url)
    
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
        resp = requests.get(url)
        if resp.status_code == 200:
            tile.source = ImageSource(StringIO(resp.content))
            return True
        if resp.status_code == 404:
            return False
        raise SourceError('%r: %r' % (resp.status_code, resp.content))
    
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
    
    def _store_with_document(self, tile, data, content_type):
        tile_document = self.tile_document(tile)
        url = self.document_url(tile.coord)
        
        tile_document['_attachments'] = {
            'tile': {
                'content_type': content_type,
                'data': data.encode('base64'),
            }
        }
        
        body = json.dumps(tile_document)
        
        resp = requests.put(url,
            headers={'Content-type': 'application/json'},
            data=body)
        
        if resp.status_code == 409:
            resp = requests.head(url)
            rev_id = resp.headers['etag'].strip('"')
            tile_document['_rev'] = rev_id
            body = json.dumps(tile_document)
            resp = requests.put(url,
                headers={'Content-type': 'application/json'},
                data=body)
        elif resp.status_code != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))
        
        return resp.headers['etag'].strip('"')
    
    def _store(self, tile, data, content_type):
        url = self.tile_url(tile.coord)
        resp = requests.put(url,
            headers={'Content-type': 'image/' + self.file_ext},
            data=data)
        if resp.status_code == 409:
            resp = requests.head(url)
            rev_id = resp.headers['etag']
            url += '?rev=' + rev_id.strip('"')
            resp = requests.put(url,
                headers={'Content-type': 'image/' + self.file_ext},
                data=data)
        elif resp.status_code != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))
    
    def store_tile(self, tile):
        if tile.stored:
            return True
            
        with tile_buffer(tile) as buf:
            data = buf.read()
            
            if self.store_document:
                self._store_with_document(tile, data, 'image/' + self.file_ext)
            else:
                self._store(tile, data, 'image/' + self.file_ext)
            return True

    def load_tile(self, tile, with_metadata=False):
        if tile.source or tile.coord is None:
            return True
        url = self.tile_url(tile.coord)
        resp = requests.get(url)
        if resp.status_code == 200:
            tile.source = ImageSource(StringIO(resp.content))
            return True
        return False
    
    def remove_tile(self, tile):
        if tile.coord is None:
            return True
        url = self.tile_url(tile.coord)
        resp = requests.head(url)
        if resp.status_code == 404:
            # already removed
            return True
        rev_id = resp.headers['etag']
        url += '?rev=' + rev_id.strip('"')
        resp = requests.delete(url)
        if resp.status_code == 200:
            return True
        return False
        
