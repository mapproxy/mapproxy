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

from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from mapproxy.cache.tile import Tile
from mapproxy.extent import MapExtent
from mapproxy.srs import SRS

try:
    import boto3
    from moto import mock_aws
except ImportError:
    boto3 = None
    mock_aws = None

from mapproxy.cache.s3 import S3Cache, S3ConnectionError
from mapproxy.test.unit.test_cache_tile import TileCacheTestBase


GLOBAL_WEBMERCATOR_EXTENT = MapExtent(
    (-20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244),
    SRS(3857))


@pytest.mark.skipif(not mock_aws or not boto3,
                    reason="boto3 and moto required for S3 tests")
class TestS3Cache(TileCacheTestBase):
    always_loads_metadata = True
    uses_utc = True

    def setup_method(self):
        TileCacheTestBase.setup_method(self)

        self.mock = mock_aws()
        self.mock.start()

        self.bucket_name = "test"
        dir_name = 'mapproxy'

        boto3.client("s3").create_bucket(Bucket=self.bucket_name)

        self.cache = S3Cache(dir_name,
                             file_ext='png',
                             directory_layout='tms',
                             bucket_name=self.bucket_name,
                             profile_name=None,
                             _concurrent_writer=1,)  # moto is not thread safe

    def teardown_method(self):
        self.mock.stop()
        TileCacheTestBase.teardown_method(self)

    def test_default_coverage(self):
        assert self.cache.coverage is None

    @pytest.mark.parametrize('layout,tile_coord,key', [
        ['mp', (12345, 67890,  2), 'mycache/webmercator/02/0001/2345/0006/7890.png'],
        ['mp', (12345, 67890, 12), 'mycache/webmercator/12/0001/2345/0006/7890.png'],

        ['tc', (12345, 67890,  2), 'mycache/webmercator/02/000/012/345/000/067/890.png'],
        ['tc', (12345, 67890, 12), 'mycache/webmercator/12/000/012/345/000/067/890.png'],

        ['tms', (12345, 67890,  2), 'mycache/webmercator/2/12345/67890.png'],
        ['tms', (12345, 67890, 12), 'mycache/webmercator/12/12345/67890.png'],

        ['quadkey', (0, 0, 0), 'mycache/webmercator/.png'],
        ['quadkey', (0, 0, 1), 'mycache/webmercator/0.png'],
        ['quadkey', (1, 1, 1), 'mycache/webmercator/3.png'],
        ['quadkey', (12345, 67890, 12), 'mycache/webmercator/200200331021.png'],

        ['arcgis', (1, 2, 3), 'mycache/webmercator/L03/R00000002/C00000001.png'],
        ['arcgis', (9, 2, 3), 'mycache/webmercator/L03/R00000002/C00000009.png'],
        ['arcgis', (10, 2, 3), 'mycache/webmercator/L03/R00000002/C0000000a.png'],
        ['arcgis', (12345, 67890, 12), 'mycache/webmercator/L12/R00010932/C00003039.png'],
    ])
    def test_tile_key(self, layout, tile_coord, key):
        cache = S3Cache('/mycache/webmercator', 'png', bucket_name=self.bucket_name, directory_layout=layout)
        cache.store_tile(self.create_tile(tile_coord))

        # raises, if key is missing
        boto3.client("s3").head_object(Bucket=self.bucket_name, Key=key)

    def test_get_bucket_url_self_hosted(self):
        tile = self.create_tile((0, 0, 1))
        key = self.cache.tile_key(tile)

        self.cache.endpoint_url = 'http://s3.example.com'
        self.cache.username = 'myuser'
        assert self.cache.get_bucket_url(tile) == \
            'http://s3.example.com/myuser:%s/%s' % (self.bucket_name, key)

        # without a username the segment is omitted
        self.cache.username = None
        assert self.cache.get_bucket_url(tile) == \
            'http://s3.example.com/%s/%s' % (self.bucket_name, key)

    def _http_get_cache(self):
        # Construct without endpoint_url so __init__'s head_bucket hits the moto
        # AWS mock; set the self-hosted endpoint afterwards for get_bucket_url.
        # The HTTP-GET path itself is exercised with _http mocked (no network).
        cache = S3Cache('mapproxy', file_ext='png', directory_layout='tms',
                        bucket_name=self.bucket_name, use_http_get=True, _concurrent_writer=1)
        cache.endpoint_url = 'http://s3.example.com'
        return cache

    def test_is_cached_http_get(self):
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        resp = mock.Mock(status=200,
                         headers={'Last-Modified': 'Wed, 21 Oct 2015 07:28:00 GMT',
                                  'Content-Length': '1234'})
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = resp
            assert cache.is_cached(tile) is True
            assert http.request.call_args[0][0] == 'HEAD'
        # the request is signed: a presigned URL, not the bare bucket URL
        requested_url = http.request.call_args[0][1]
        assert requested_url != cache.get_bucket_url(tile)
        assert 'Signature=' in requested_url
        # metadata parsed from the HTTP response headers
        assert tile.size == 1234
        assert tile.timestamp is not None

    def test_is_cached_http_get_missing(self):
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=404)
            assert cache.is_cached(tile) is False

    def test_load_tile_http_get(self):
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        resp = mock.Mock(status=200, data=b'\x89PNG\r\n\x1a\n')
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = resp
            assert cache.load_tile(tile) is True
            assert http.request.call_args[0][0] == 'GET'
        # the request is signed: a presigned URL, not the bare bucket URL
        requested_url = http.request.call_args[0][1]
        assert requested_url != cache.get_bucket_url(tile)
        assert 'Signature=' in requested_url
        assert tile.image_result is not None
        assert not tile.is_missing()

    def test_load_tile_http_get_missing(self):
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=404)
            assert cache.load_tile(tile) is False

    @pytest.mark.parametrize('method,status', [
        ('HEAD', 500), ('GET', 500),
        # a genuine 403 on a signed request is a real error, not a cache miss
        ('HEAD', 403), ('GET', 403),
    ])
    def test_http_get_error_status_raises(self, method, status):
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=status, data=b'')
            with pytest.raises(S3ConnectionError):
                if method == 'HEAD':
                    cache.is_cached(tile)
                else:
                    cache.load_tile(tile)

    @pytest.mark.parametrize('method', ['HEAD', 'GET'])
    def test_http_get_404_is_cache_miss_not_error(self, method):
        # 404 must remain a normal cache miss, unlike 403, even though both
        # were previously grouped together
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=404, data=b'')
            if method == 'HEAD':
                assert cache.is_cached(tile) is False
            else:
                assert cache.load_tile(tile) is False

    def test_http_get_uses_presigned_url_not_bucket_url(self):
        # Bucket/Key addressing must match the boto3 write path — the
        # {endpoint}/{username}:{bucket}/{key} convention is retired here.
        cache = self._http_get_cache()
        cache.username = 'myuser'
        tile = Tile((0, 0, 1))
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=404, data=b'')
            cache.is_cached(tile)
        requested_url = http.request.call_args[0][1]
        assert 'myuser:' not in requested_url
        assert cache.bucket_name in requested_url

    def test_http_get_logs_key_not_url(self, caplog):
        # debug logs must not print the full request URL, which would carry
        # the presigned signature
        cache = self._http_get_cache()
        tile = Tile((0, 0, 1))
        key = cache.tile_key(tile)
        with mock.patch('mapproxy.cache.s3._http') as http:
            http.request.return_value = mock.Mock(status=404, data=b'')
            with caplog.at_level('DEBUG', logger='mapproxy.cache.s3'):
                cache.is_cached(tile)
        assert any(key in record.getMessage() and 'Signature=' not in record.getMessage()
                   for record in caplog.records)

    def test_set_metadata_boto3_and_http_agree(self):
        # boto3 spells the keys LastModified/ContentLength with typed values,
        # the HTTP path spells them Last-Modified/Content-Length as strings.
        # Both must yield identical tile metadata.
        boto_tile, http_tile = Tile((0, 0, 1)), Tile((0, 0, 1))
        self.cache._set_metadata(
            {'LastModified': datetime(2015, 10, 21, 7, 28, tzinfo=timezone.utc),
             'ContentLength': 1234}, boto_tile)
        self.cache._set_metadata(
            {'Last-Modified': 'Wed, 21 Oct 2015 07:28:00 GMT',
             'Content-Length': '1234'}, http_tile)

        assert boto_tile.timestamp == http_tile.timestamp
        assert boto_tile.size == http_tile.size == 1234

    def test_set_metadata_honours_utc_offset(self):
        # a non-UTC offset must be normalized, not dropped
        offset_tile, utc_tile = Tile((0, 0, 1)), Tile((0, 0, 1))
        self.cache._set_metadata({'Last-Modified': 'Wed, 21 Oct 2015 09:28:00 +0200'}, offset_tile)
        self.cache._set_metadata({'Last-Modified': 'Wed, 21 Oct 2015 07:28:00 GMT'}, utc_tile)
        assert offset_tile.timestamp == utc_tile.timestamp

        aware_tile = Tile((0, 0, 1))
        self.cache._set_metadata(
            {'LastModified': datetime(2015, 10, 21, 9, 28,
                                      tzinfo=timezone(timedelta(hours=2)))}, aware_tile)
        assert aware_tile.timestamp == utc_tile.timestamp

    def test_set_metadata_ignores_unparsable_values(self):
        tile = Tile((0, 0, 1))
        self.cache._set_metadata({'Last-Modified': 'not a date', 'Content-Length': 'huge'}, tile)
        assert tile.timestamp is None
        assert tile.size is None
