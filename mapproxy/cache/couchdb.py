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
        
    def document_url(self, coord, relative=False):
        x, y, z = coord
        matrix_set = self.tile_grid.name
        couch_url = self.couch_url
        if relative:
            if self.tile_path_template:
                if self.tile_path_template.startswith('%(couch_url)s/'):
                    tile_path_template = self.tile_path_template[len('%(couch_url)s/'):]
                else:
                    tile_path_template = self.tile_path_template
                return tile_path_template % locals()
            else:
                return '%(matrix_set)s-%(z)d-%(x)d-%(y)d' % locals()
        else:
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
    
    def _store_bulk(self, tiles):
        tile_docs = {}
        for tile in tiles:
            tile_id = self.document_url(tile.coord, relative=True)
            tile_doc = {'_id': tile_id}
            with tile_buffer(tile) as buf:
                data = buf.read()
            tile_doc['_attachments'] = {
                'tile': {
                    'content_type': 'image/' + self.file_ext,
                    'data': data.encode('base64'),
                }
            }
            tile_docs[tile_id] = tile_doc
        
        duplicate_tiles = self._post_bulk(tile_docs)

        if duplicate_tiles:
            self._fill_rev_ids(duplicate_tiles)
            self._post_bulk(duplicate_tiles, no_conflicts=True)
            
        return True
    
    def _post_bulk(self, tile_docs, no_conflicts=False):
        """
        POST multiple tiles, returns all tile docs with conflicts during POST.
        """
        doc = {'docs': tile_docs.values()}
        data = json.dumps(doc)
        resp = requests.post(self.couch_url + '/_bulk_docs', data=data, headers={'Content-type': 'application/json'})
        if resp.status_code != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))
        
        resp_doc = json.loads(resp.content)
        duplicate_tiles = {}
        for tile in resp_doc:
            if tile.get('error', 'false') == 'conflict':
                duplicate_tiles[tile['id']] = tile_docs[tile['id']]
        
        if no_conflicts and duplicate_tiles:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))
        
        return duplicate_tiles
    
    def _fill_rev_ids(self, tile_docs):
        """
        Request all revs for tile_docs and insert it into the tile_docs.
        """
        keys_doc = {'keys': tile_docs.keys()}
        data = json.dumps(keys_doc)
        resp = requests.post(self.couch_url + '/_all_docs', data=data, headers={'Content-type': 'application/json'})
        if resp.status_code != 200:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))
        
        resp_doc = json.loads(resp.content)
        for tile in resp_doc['rows']:
            tile_docs[tile['id']]['_rev'] = tile['value']['rev']
    
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

    def store_tiles(self, tiles):
        tiles = [t for t in tiles if not t.stored]
        print tiles
        return self._store_bulk(tiles)

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
        
