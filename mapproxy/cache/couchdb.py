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


import codecs
import datetime
import json
import socket
import time
import hashlib
import base64

from mapproxy.image import ImageSource
from mapproxy.cache.base import (
    TileCacheBase,
    tile_buffer, CacheBackendError,)
from mapproxy.source import SourceError
from mapproxy.srs import SRS
from mapproxy.compat import string_type, iteritems, BytesIO

from threading import Lock

try:
    import requests
except ImportError:
    requests = None


import logging
log = logging.getLogger(__name__)

class UnexpectedResponse(CacheBackendError):
    pass

class CouchDBCache(TileCacheBase):
    def __init__(self, url, db_name,
        file_ext, tile_grid, md_template=None,
        tile_id_template=None):

        if requests is None:
            raise ImportError("CouchDB backend requires 'requests' package.")

        self.lock_cache_id = 'couchdb-' + hashlib.md5((url + db_name).encode('utf-8')).hexdigest()
        self.file_ext = file_ext
        self.tile_grid = tile_grid
        self.md_template = md_template
        self.couch_url = '%s/%s' % (url.rstrip('/'), db_name.lower())
        self.req_session = requests.Session()
        self.req_session.timeout = 5
        self.db_initialised = False
        self.app_init_db_lock = Lock()
        self.tile_id_template = tile_id_template

    def init_db(self):
        with self.app_init_db_lock:
            if self.db_initialised:
                return
            try:
                self.req_session.put(self.couch_url)
                self.db_initialised = True
            except requests.exceptions.RequestException as ex:
                log.warning('unable to initialize CouchDB: %s', ex)

    def tile_url(self, coord):
        return self.document_url(coord) + '/tile'

    def document_url(self, coord, relative=False):
        x, y, z = coord
        grid_name = self.tile_grid.name
        couch_url = self.couch_url
        if relative:
            if self.tile_id_template:
                if self.tile_id_template.startswith('%(couch_url)s/'):
                    tile_id_template = self.tile_id_template[len('%(couch_url)s/'):]
                else:
                    tile_id_template = self.tile_id_template
                return tile_id_template % locals()
            else:
                return '%(grid_name)s-%(z)s-%(x)s-%(y)s' % locals()
        else:
            if self.tile_id_template:
                return self.tile_id_template % locals()
            else:
                return '%(couch_url)s/%(grid_name)s-%(z)s-%(x)s-%(y)s' % locals()

    def is_cached(self, tile):
        if tile.coord is None or tile.source:
            return True
        url = self.document_url(tile.coord)
        try:
            self.init_db()
            resp = self.req_session.get(url)
            if resp.status_code == 200:
                doc = json.loads(codecs.decode(resp.content, 'utf-8'))
                tile.timestamp = doc.get(self.md_template.timestamp_key)
                return True
        except (requests.exceptions.RequestException, socket.error) as ex:
            # is_cached should not fail (would abort seeding for example),
            # so we catch these errors here and just return False
            log.warning('error while requesting %s: %s', url, ex)
            return False
        if resp.status_code == 404:
            return False
        raise SourceError('%r: %r' % (resp.status_code, resp.content))


    def _tile_doc(self, tile):
        tile_id = self.document_url(tile.coord, relative=True)
        if self.md_template:
            tile_doc = self.md_template.doc(tile, self.tile_grid)
        else:
            tile_doc = {}
        tile_doc['_id'] = tile_id

        with tile_buffer(tile) as buf:
            data = buf.read()
        tile_doc['_attachments'] = {
            'tile': {
                'content_type': 'image/' + self.file_ext,
                'data': codecs.decode(
                    base64.b64encode(data).replace(b'\n', b''),
                    'ascii',
                ),
            }
        }
        return tile_id, tile_doc

    def _store_bulk(self, tiles):
        tile_docs = {}
        for tile in tiles:
            tile_id, tile_doc = self._tile_doc(tile)
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
        doc = {'docs': list(tile_docs.values())}
        data = json.dumps(doc)
        self.init_db()
        resp = self.req_session.post(self.couch_url + '/_bulk_docs', data=data, headers={'Content-type': 'application/json'})
        if resp.status_code != 201:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))

        resp_doc = json.loads(codecs.decode(resp.content, 'utf-8'))
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
        keys_doc = {'keys': list(tile_docs.keys())}
        data = json.dumps(keys_doc)
        self.init_db()
        resp = self.req_session.post(self.couch_url + '/_all_docs', data=data, headers={'Content-type': 'application/json'})
        if resp.status_code != 200:
            raise UnexpectedResponse('got unexpected resp (%d) from CouchDB: %s' % (resp.status_code, resp.content))

        resp_doc = json.loads(codecs.decode(resp.content, 'utf-8'))
        for tile in resp_doc['rows']:
            tile_docs[tile['id']]['_rev'] = tile['value']['rev']

    def store_tile(self, tile):
        if tile.stored:
            return True

        return self._store_bulk([tile])

    def store_tiles(self, tiles):
        tiles = [t for t in tiles if not t.stored]
        return self._store_bulk(tiles)

    def load_tile_metadata(self, tile):
        if tile.timestamp:
            return

        # is_cached loads metadata
        self.is_cached(tile)

    def load_tile(self, tile, with_metadata=False):
        # bulk loading with load_tiles is not implemented, because
        # CouchDB's /all_docs? does not include attachments

        if tile.source or tile.coord is None:
            return True
        url = self.document_url(tile.coord) + '?attachments=true'
        self.init_db()
        resp = self.req_session.get(url, headers={'Accept': 'application/json'})
        if resp.status_code == 200:
            doc = json.loads(codecs.decode(resp.content, 'utf-8'))
            tile_data = BytesIO(base64.b64decode(doc['_attachments']['tile']['data']))
            tile.source = ImageSource(tile_data)
            tile.timestamp = doc.get(self.md_template.timestamp_key)
            return True
        return False

    def remove_tile(self, tile):
        if tile.coord is None:
            return True
        url = self.document_url(tile.coord)
        resp = requests.head(url)
        if resp.status_code == 404:
            # already removed
            return True
        rev_id = resp.headers['etag']
        url += '?rev=' + rev_id.strip('"')
        self.init_db()
        resp = self.req_session.delete(url)
        if resp.status_code == 200:
            return True
        return False


def utc_now_isoformat():
    now = datetime.datetime.utcnow()
    now = now.isoformat()
    # remove milliseconds, add Zulu timezone
    now = now.rsplit('.', 1)[0] + 'Z'
    return now

class CouchDBMDTemplate(object):
    def __init__(self, attributes):
        self.attributes = attributes
        for key, value in iteritems(attributes):
            if value == '{{timestamp}}':
                self.timestamp_key = key
                break
        else:
            attributes['timestamp'] = '{{timestamp}}'
            self.timestamp_key = 'timestamp'

    def doc(self, tile, grid):
        doc = {}
        x, y, z = tile.coord
        for key, value in iteritems(self.attributes):
            if not isinstance(value, string_type) or not value.startswith('{{'):
                doc[key] = value
                continue

            if value == '{{timestamp}}':
                doc[key] = time.time()
            elif value == '{{x}}':
                doc[key] = x
            elif value == '{{y}}':
                doc[key] = y
            elif value in ('{{z}}', '{{level}}'):
                doc[key] = z
            elif value == '{{utc_iso}}':
                doc[key] = utc_now_isoformat()
            elif value == '{{wgs_tile_centroid}}':
                tile_bbox = grid.tile_bbox(tile.coord)
                centroid = (
                    tile_bbox[0] + (tile_bbox[2]-tile_bbox[0])/2,
                    tile_bbox[1] + (tile_bbox[3]-tile_bbox[1])/2
                )
                centroid = grid.srs.transform_to(SRS(4326), centroid)
                doc[key] = centroid
            elif value == '{{tile_centroid}}':
                tile_bbox = grid.tile_bbox(tile.coord)
                centroid = (
                    tile_bbox[0] + (tile_bbox[2]-tile_bbox[0])/2,
                    tile_bbox[1] + (tile_bbox[3]-tile_bbox[1])/2
                )
                doc[key] = centroid
            else:
                raise ValueError('unknown CouchDB tile_metadata value: %r' % (value, ))
        return doc
