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

from __future__ import division

import sys

from io import BytesIO

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.system import SysTest

import pytest


try:
    import boto3
    from moto import mock_s3
except ImportError:
    boto3 = None
    mock_s3 = None


@pytest.fixture(scope="module")
def config_file():
    return "cache_s3.yaml"


@pytest.fixture(scope="module")
def s3_buckets():
    with mock_s3():
        boto3.client("s3").create_bucket(Bucket="default_bucket")
        boto3.client("s3").create_bucket(Bucket="tiles")
        boto3.client("s3").create_bucket(Bucket="reversetiles")

        yield


@pytest.mark.skipif(not (boto3 and mock_s3), reason="boto3 and moto required")
@pytest.mark.xfail(
    sys.version_info[:2] in ((3, 4), (3, 5)),
    reason="moto tests unreliable with Python 3.4/3.5",
)
@pytest.mark.usefixtures("s3_buckets")
class TestS3Cache(SysTest):

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-150,-40,-140,-30",
                width="100",
                height="100",
                layers="default",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

    def test_get_map_cached(self, app):
        # mock_s3 interferes with MockServ, use boto to manually upload tile
        tile = create_tmp_image((256, 256))
        boto3.client("s3").upload_fileobj(
            BytesIO(tile),
            Bucket="default_bucket",
            Key="default_cache/WebMerc/4/1/9.png",
        )

        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_cached_quadkey(self, app):
        # mock_s3 interferes with MockServ, use boto to manually upload tile
        tile = create_tmp_image((256, 256))
        boto3.client("s3").upload_fileobj(
            BytesIO(tile), Bucket="tiles", Key="quadkeytiles/2003.png"
        )

        self.common_map_req.params.layers = "quadkey"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_cached_reverse_tms(self, app):
        # mock_s3 interferes with MockServ, use boto to manually upload tile
        tile = create_tmp_image((256, 256))
        boto3.client("s3").upload_fileobj(
            BytesIO(tile), Bucket="tiles", Key="reversetiles/9/1/4.png"
        )

        self.common_map_req.params.layers = "reverse"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
