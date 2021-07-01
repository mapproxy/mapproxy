# This file is part of the MapProxy project.
# Copyright (C) 2010-2012 Omniscale <http://omniscale.de>
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

import os
import time
import hashlib

from io import BytesIO
import pytest

from mapproxy.compat.image import Image
from mapproxy.test.image import is_jpeg, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system import SysTest
from mapproxy.util.times import timestamp_from_isodate

@pytest.fixture(scope="module")
def config_file():
    return "tileservice_refresh.yaml"


class TestRefresh(SysTest):

    def test_refresh_tile_1s(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                file_path = cache_dir.join(
                    "wms_cache_EPSG900913/01/000/000/000/000/000/000.jpeg"
                )
                assert file_path.check()
                t1 = file_path.mtime()
                # file_path.remove()
                # assert not file_path.check()
            resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
            assert resp.content_type == "image/jpeg"
            assert file_path.check()
            t2 = file_path.mtime()
            # tile is expired after 1 sec, so it will be fetched again from mock server
            time.sleep(1.2)
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                assert file_path.check()
                t3 = file_path.mtime()
        assert t2 == t1
        assert t3 > t2

    def test_refresh_tile_mtime(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache_isotime/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                file_path = cache_dir.join(
                    "wms_cache_isotime_EPSG900913/01/000/000/000/000/000/000.jpeg"
                )
                assert file_path.check()
                timestamp = timestamp_from_isodate("2009-02-15T23:31:30")
                file_path.setmtime(timestamp + 1.2)
                t1 = file_path.mtime()
            resp = app.get("/tiles/wms_cache_isotime/1/0/0.jpeg")
            assert resp.content_type == "image/jpeg"
            t2 = file_path.mtime()
            file_path.setmtime(timestamp - 1.2)
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache_isotime/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                assert file_path.check()
                t3 = file_path.mtime()
            assert t2 == t1
            assert t3 > t2

    def test_refresh_tile_source_error_no_stale(self, app, cache_dir):
        source_request = {
            "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
            "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
            "&WIDTH=256"
        }
        with tmp_image((256, 256), format="png") as img:
            expected_req = (
                source_request,
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache_png/1/0/0.png")
                assert resp.content_type == "image/png"
                img.seek(0)
                assert resp.body == img.read()
            resp = app.get("/tiles/wms_cache_png/1/0/0.png")
            assert resp.content_type == "image/png"
            img.seek(0)
            assert resp.body == img.read()
            # tile is expired after 1 sec, so it will be requested again from mock server
            time.sleep(1.2)
            expected_req = (
                source_request,
                {"body": "", "status": 404},
            )
            with mock_httpd(
                    ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache_png/1/0/0.png")
                assert resp.content_type == "image/png"
                # error handler for 404 does not authorise stale tiles, so transparent tile will be rendered
                resp_img = Image.open(BytesIO(resp.body))
                # check response transparency
                assert resp_img.getbands() == ('R', 'G', 'B', 'A')
                assert resp_img.getextrema()[3] == (0, 0)

            expected_req = (
                source_request,
                {"body": "", "status": 405},
            )
            with mock_httpd(
                    ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache_png/1/0/0.png")
                assert resp.content_type == "image/png"
                # error handler for 405 does not authorise stale tiles, so red tile will be rendered
                resp_img = Image.open(BytesIO(resp.body))
                # check response red color
                assert resp_img.getbands() == ('R', 'G', 'B')
                assert resp_img.getextrema() == ((255, 255), (0, 0), (0, 0))

    def test_refresh_tile_source_error_stale(self, app, cache_dir):
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/jpeg"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                img.seek(0)
                assert resp.body == img.read()
            resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
            assert resp.content_type == "image/jpeg"
            img.seek(0)
            assert resp.body == img.read()
            # tile is expired after 1 sec, so it will be fetched again from mock server
            time.sleep(1.2)
            expected_req = (
                {
                    "path": r"/service?LAYERs=bar&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=-20037508.3428,-20037508.3428,0.0,0.0"
                    "&WIDTH=256"
                },
                {"body": "", "status": 406},
            )
            with mock_httpd(
                    ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get("/tiles/wms_cache/1/0/0.jpeg")
                assert resp.content_type == "image/jpeg"
                # Check that initial non empty img is served as a stale tile
                img.seek(0)
                assert resp.body == img.read()
