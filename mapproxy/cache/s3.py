from __future__ import with_statement

import sys
from mapproxy.image import ImageSource
from mapproxy.cache.base import tile_buffer
from mapproxy.cache.file import FileCache
from mapproxy.util.py import reraise_exception

try:
    import boto3
    import botocore
except ImportError:
    boto3 = None

from io import BytesIO

import logging
log = logging.getLogger('mapproxy.cache.s3')


def connect(profile_name=None):
    if boto3 is None:
        raise ImportError("S3 Cache requires 'boto3' package.")

    try:
        return boto3.client("s3")
    except Exception as e:
        raise S3ConnectionError('Error during connection %s' % e)

class S3ConnectionError(Exception):
    pass

class S3Cache(FileCache):
    def __init__(self, cache_dir, file_ext, lock_dir=None, directory_layout='tms',
                 lock_timeout=60.0, bucket_name='mapproxy', profile_name=None):
        self.conn = connect()
        self.bucket_name = bucket_name
        try:
            self.bucket = self.conn.head_bucket(Bucket=bucket_name)
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

        super(S3Cache, self).__init__(cache_dir,
            file_ext=file_ext,
            directory_layout=directory_layout,
            lock_timeout=lock_timeout,
            link_single_color_images=False,
        )


    def load_tile_metadata(self, tile):
        # TODO Implement storing / retrieving tile metadata
        tile.timestamp = 0
        tile.size = 0

    def is_cached(self, tile):
        """
        Returns ``True`` if the tile data is present.
        """
        if tile.is_missing():
            location = self.tile_location(tile)

            try:
                self.conn.head_object(Bucket=self.bucket_name, Key=location)
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return False
                raise

        return True

    def load_tile(self, tile, with_metadata=False):
        """
        Fills the `Tile.source` of the `tile` if it is cached.
        If it is not cached or if the ``.coord`` is ``None``, nothing happens.
        """
        if not tile.is_missing():
            return True

        location = self.tile_location(tile)
        log.debug('S3:load_tile, location: %s' % location)

        tile_data = BytesIO()
        try:
            self.conn.download_fileobj(self.bucket_name, location, tile_data)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
        tile.source = ImageSource(tile_data)

        return True

    def remove_tile(self, tile):
        location = self.tile_location(tile)
        log.debug('remove_tile, location: %s' % location)

        self.conn.delete_object(Bucket=self.bucket_name, Key=location)

    def store_tile(self, tile):
        """
        Add the given `tile` to the file cache. Stores the `Tile.source` to
        `FileCache.tile_location`.
        """
        if tile.stored:
            return

        location = self.tile_location(tile)
        log.debug('S3: store_tile, location: %s' % location)

        extra_args = {}
        if self.file_ext in ('jpeg', 'png'):
            extra_args['ContentType'] = 'image/' + self.file_ext
        with tile_buffer(tile) as buf:
            self.conn.upload_fileobj(
                NopCloser(buf), # upload_fileobj closes buf, wrap in NopCloser
                self.bucket_name,
                location,
                ExtraArgs=extra_args)


        # Attempt making storing tiles non-blocking

        # This is still blocking when I thought that it would not
        # async.run_non_blocking(self.async_store, (k, tile))

        # async_pool = async.Pool(4)
        # for store in async_pool.map(self.async_store_, [(k, tile)]):
        #     log.debug('stored...')

        # This sometimes suffers from "ValueError: I/O operation on closed file"
        # as I guess it's not advised to use threads within a wsgi app
        # Timer(0.25, self.async_store, args=[k, tile]).start()

    def async_store_(self, foo):
        key, tile = foo
        print 'Storing %s, %s' % (key, tile)
        with tile_buffer(tile) as buf:
            key.set_contents_from_file(buf)

    def async_store(self, key, tile):
        print 'Storing %s, %s' % (key, tile)
        with tile_buffer(tile) as buf:
            key.set_contents_from_file(buf)

class NopCloser(object):
    def __init__(self, wrapped):
        self.wrapped = wrapped

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self.wrapped, name)