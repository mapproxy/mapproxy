# This file is part of the MapProxy project.
# Copyright (C) 2016 Omniscale <http://omniscale.de>
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


import calendar
import hashlib
import sys
import threading

from mapproxy.image import ImageSource
from mapproxy.cache import path
from mapproxy.cache.base import tile_buffer, TileCacheBase
from mapproxy.util import async_
from mapproxy.util.py import reraise_exception

try:
    import boto3
    import botocore
except ImportError:
    boto3 = None


import logging
log = logging.getLogger('mapproxy.cache.s3')


_s3_sessions_cache = threading.local()
def s3_session(profile_name=None):
    if not hasattr(_s3_sessions_cache, 'sessions'):
        _s3_sessions_cache.sessions = {}
    if profile_name not in _s3_sessions_cache.sessions:
        _s3_sessions_cache.sessions[profile_name] = boto3.session.Session(profile_name=profile_name)
    return _s3_sessions_cache.sessions[profile_name]

class S3ConnectionError(Exception):
    pass

class S3Cache(TileCacheBase):

    def __init__(self, base_path, file_ext, directory_layout='tms',
                 bucket_name='mapproxy', profile_name=None, region_name=None, endpoint_url=None,
                 _concurrent_writer=4, access_control_list=None):
        super(S3Cache, self).__init__()
        self.lock_cache_id = hashlib.md5(base_path.encode('utf-8') + bucket_name.encode('utf-8')).hexdigest()
        self.bucket_name = bucket_name
        self.profile_name = profile_name
        self.region_name = region_name
        self.endpoint_url = endpoint_url
        self.access_control_list = access_control_list

        try:
            self.bucket = self.conn().head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise S3ConnectionError('No such bucket: %s' % bucket_name)
            elif e.response['Error']['Code'] == '403':
                raise S3ConnectionError('Access denied. Check your credentials')
            else:
                reraise_exception(
                    S3ConnectionError('Unknown error: %s' % e),
                    sys.exc_info(),
                )

        self.base_path = base_path
        self.file_ext = file_ext
        self._concurrent_writer = _concurrent_writer

        self._tile_location, _ = path.location_funcs(layout=directory_layout)

    def tile_key(self, tile):
        return self._tile_location(tile, self.base_path, self.file_ext).lstrip('/')

    def conn(self):
        if boto3 is None:
            raise ImportError("S3 Cache requires 'boto3' package.")

        try:
            return s3_session(self.profile_name).client("s3", region_name=self.region_name, endpoint_url=self.endpoint_url)
        except Exception as e:
            raise S3ConnectionError('Error during connection %s' % e)

    def load_tile_metadata(self, tile):
        if tile.timestamp:
            return
        self.is_cached(tile)

    def _set_metadata(self, response, tile):
        if 'LastModified' in response:
            tile.timestamp = calendar.timegm(response['LastModified'].timetuple())
        if 'ContentLength' in response:
            tile.size = response['ContentLength']

    def is_cached(self, tile):
        if tile.is_missing():
            key = self.tile_key(tile)
            try:
                r = self.conn().head_object(Bucket=self.bucket_name, Key=key)
                self._set_metadata(r, tile)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] in ('404', 'NoSuchKey'):
                    return False
                raise

        return True

    def load_tiles(self, tiles, with_metadata=True):
        p = async_.Pool(min(4, len(tiles)))
        return all(p.map(self.load_tile, tiles))

    def load_tile(self, tile, with_metadata=True):
        if not tile.is_missing():
            return True

        key = self.tile_key(tile)
        log.debug('S3:load_tile, key: %s' % key)

        try:
            r  = self.conn().get_object(Bucket=self.bucket_name, Key=key)
            self._set_metadata(r, tile)
            tile.source = ImageSource(r['Body'])
        except botocore.exceptions.ClientError as e:
            error = e.response.get('Errors', e.response)['Error'] # moto get_object can return Error wrapped in Errors...
            if error['Code'] in ('404', 'NoSuchKey'):
                return False
            raise

        return True

    def remove_tile(self, tile):
        key = self.tile_key(tile)
        log.debug('remove_tile, key: %s' % key)
        self.conn().delete_object(Bucket=self.bucket_name, Key=key)

    def store_tiles(self, tiles):
        p = async_.Pool(min(self._concurrent_writer, len(tiles)))
        p.map(self.store_tile, tiles)

    def store_tile(self, tile):
        if tile.stored:
            return

        key = self.tile_key(tile)
        log.debug('S3: store_tile, key: %s' % key)

        extra_args = {}
        if self.file_ext in ('jpeg', 'png'):
            extra_args['ContentType'] = 'image/' + self.file_ext
        if self.access_control_list:
            extra_args['ACL'] = self.access_control_list
        with tile_buffer(tile) as buf:
            self.conn().upload_fileobj(
                NopCloser(buf), # upload_fileobj closes buf, wrap in NopCloser
                self.bucket_name,
                key,
                ExtraArgs=extra_args)

class NopCloser(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self.wrapped, name)
