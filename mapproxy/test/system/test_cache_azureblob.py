# This file is part of the MapProxy project.
# Copyright (C) 2022 Omniscale <http://omniscale.de>
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

import os
from io import BytesIO

import pytest

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.test.image import is_png, create_tmp_image
from mapproxy.test.system import SysTest

try:
    from mapproxy.cache.azureblob import AzureBlobCache
except ImportError:
    AzureBlobCache = None


def azureblob_connection():
    # Use default storage account of Azurite emulator
    host = os.environ['MAPPROXY_TEST_AZURE_BLOB']
    return 'DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=' \
           'Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr' \
           '/KBHBeksoGMGw==;BlobEndpoint=' + host + '/devstoreaccount1;'


def azure_container_client(connection_string, container_name):
    return AzureBlobCache(
        base_path="",
        file_ext="",
        connection_string=connection_string,
        container_name=container_name).container_client


@pytest.fixture(scope="module")
def config_file():
    return "cache_azureblob.yaml"


@pytest.fixture(scope="module")
def azureblob_containers():
    container = azure_container_client(azureblob_connection(), 'default-container')
    if not container.exists():
        container.create_container()
    container = azure_container_client(azureblob_connection(), 'tiles')
    if not container.exists():
        container.create_container()

    yield


@pytest.mark.skipif(not AzureBlobCache or not os.environ.get('MAPPROXY_TEST_AZURE_BLOB'),
                    reason="azure-storage-blob package and MAPPROXY_TEST_AZURE_BLOB env required")
@pytest.mark.usefixtures("azureblob_containers")
class TestAzureBlobCache(SysTest):

    def setup_method(self):
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
        tile = create_tmp_image((256, 256))
        container = azure_container_client(azureblob_connection(), 'default-container')
        container.upload_blob(
            name="default_cache/WebMerc/4/1/9.png",
            data=BytesIO(tile),
            overwrite=True
        )
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_cached_quadkey(self, app):
        tile = create_tmp_image((256, 256))
        container = azure_container_client(azureblob_connection(), 'tiles')
        container.upload_blob(
            name="quadkeytiles/2003.png",
            data=BytesIO(tile),
            overwrite=True
        )
        self.common_map_req.params.layers = "quadkey"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)

    def test_get_map_cached_reverse_tms(self, app):
        tile = create_tmp_image((256, 256))
        container = azure_container_client(azureblob_connection(), 'tiles')
        container.upload_blob(
            name="reversetiles/9/1/4.png",
            data=BytesIO(tile),
            overwrite=True
        )
        self.common_map_req.params.layers = "reverse"
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
