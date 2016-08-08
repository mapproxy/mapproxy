from __future__ import with_statement

import os
from mapproxy.image import ImageSource
from mapproxy.cache.base import tile_buffer
from mapproxy.cache.file import FileCache

try:
    import boto
except ImportError:
    boto = None

import StringIO

import logging
log = logging.getLogger('mapproxy.cache.s3')

s3_connection = None

class S3Connection:
    def __init__(self, profile_name=None):
        if boto is None:
            raise ImportError("S3 Cache requires 'boto' package.")
        self.conn = None
        self.profile_name = profile_name

    def get(self):
        if self.conn is None:
            if self.profile_name is not None:
                try:
                    self.conn = boto.connect_s3(profile_name=self.profile_name)
                except boto.provider.ProfileNotFoundError:
                    raise Error('S3: Profile no found %s' % e)
                except Exception as e:
                    raise Error('S3: Error during connection %s' % e)
            else:
                try:
                    self.conn = boto.connect_s3()
                except boto.exception.NoAuthHandlerFound as e:
                    raise Error('S3: No handler found %s' % e)

        return self.conn



class S3Cache(FileCache):

    """
    This class is responsible to store and load the actual tile data.
    """

    def __init__(self, cache_dir, file_ext, lock_dir=None, directory_layout='tms',
                 lock_timeout=60.0, bucket_name='mapproxy', profile_name=None):
        """
        :param cache_dir: the path where the tile will be stored
        :param file_ext: the file extension that will be appended to
            each tile (e.g. 'png')
        """
        global s3_connection

        if s3_connection is None:
            s3_connection = S3Connection(profile_name=profile_name)

        conn = s3_connection.get()

        try:
            self.bucket = conn.get_bucket(bucket_name)
        except boto.exception.S3ResponseError as e:
            log.error("Fuck %s" % e.error_code)
            if e.error_code == 'NoSuchBucket':
                log.error('No such bucket: %s' % bucket_name)
                raise e
            elif e.error_code == 'AccessDenied':
                log.error('Access denied. Check your credentials')
                raise e
            else:
                log.error('Unknown error %e' % e)
                raise e

        super(S3Cache, self).__init__(cache_dir, file_ext=file_ext, directory_layout=directory_layout, lock_timeout=lock_timeout, link_single_color_images=False)


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

            k = boto.s3.key.Key(self.bucket)
            k.key = location
            if k.exists():
                log.debug('S3: cache HIT, location: %s' % location)
                return True
            else:
                log.debug('S3: cache MISS, location: %s' % location)
                return False
        else:
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

        tile_data = StringIO.StringIO()
        k = boto.s3.key.Key(self.bucket)
        k.key = location
        try:
            k.get_contents_to_file(tile_data)
            tile.source = ImageSource(tile_data)
            k.close()
            return True
        except boto.exception.S3ResponseError:
            # NoSuchKey
            pass
        k.close()
        return False

    def remove_tile(self, tile):

        location = self.tile_location(tile)
        log.debug('remove_tile, location: %s' % location)

        k = boto.s3.key.Key(self.bucket)
        k.key = location
        if k.exists():
            k.delete()
        k.close()

    def store_tile(self, tile):
        """
        Add the given `tile` to the file cache. Stores the `Tile.source` to
        `FileCache.tile_location`.
        """
        if tile.stored:
            return

        location = self.tile_location(tile)
        log.debug('S3: store_tile, location: %s' % location)

        k = boto.s3.key.Key(self.bucket)
        if self.file_ext in ('jpeg', 'png'):
            k.content_type = 'image/' + self.file_ext
        k.key = location
        with tile_buffer(tile) as buf:
            k.set_contents_from_file(buf)
        k.close()

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
