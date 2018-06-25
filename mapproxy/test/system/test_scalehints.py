# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
import math

import pytest

from mapproxy.request.wms import (
    WMS111MapRequest,
    WMS111CapabilitiesRequest,
    WMS130CapabilitiesRequest,
)

from mapproxy.test.system import SysTest
from mapproxy.test.image import is_png, is_transparent, tmp_image
from mapproxy.test.http import mock_httpd
from mapproxy.test.system.test_wms import is_111_capa, is_130_capa, ns130


@pytest.fixture(scope="module")
def config_file():
    return "scalehints.yaml"


def diagonal_res_to_pixel_res(res):
    """
    >>> '%.2f' % round(diagonal_res_to_pixel_res(14.14214), 4)
    '10.00'
    """
    return math.sqrt((float(res) ** 2) / 2)


class TestWMS(SysTest):

    def setup(self):
        self.common_req = WMS111MapRequest(
            url="/service?", param=dict(service="WMS", version="1.1.1")
        )
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="res",
                srs="EPSG:4326",
                format="image/png",
                transparent="true",
                styles="",
                request="GetMap",
            ),
        )

    def test_capabilities_111(self, app):
        req = WMS111CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        xml = resp.lxml
        assert is_111_capa(xml)
        hints = xml.xpath("//Layer/Layer/ScaleHint")
        assert diagonal_res_to_pixel_res(hints[0].attrib["min"]) == pytest.approx(10)
        assert diagonal_res_to_pixel_res(hints[0].attrib["max"]) == pytest.approx(10000)

        assert diagonal_res_to_pixel_res(hints[1].attrib["min"]) == pytest.approx(2.8)
        assert diagonal_res_to_pixel_res(hints[1].attrib["max"]) == pytest.approx(280)

        assert diagonal_res_to_pixel_res(hints[2].attrib["min"]) == pytest.approx(0.28)
        assert diagonal_res_to_pixel_res(hints[2].attrib["max"]) == pytest.approx(2.8)

    def test_capabilities_130(self, app):
        req = WMS130CapabilitiesRequest(url="/service?").copy_with_request_params(
            self.common_req
        )
        resp = app.get(req)
        xml = resp.lxml
        assert is_130_capa(xml)
        min_scales = xml.xpath(
            "//wms:Layer/wms:Layer/wms:MinScaleDenominator/text()", namespaces=ns130
        )
        max_scales = xml.xpath(
            "//wms:Layer/wms:Layer/wms:MaxScaleDenominator/text()", namespaces=ns130
        )

        assert float(min_scales[0]) == pytest.approx(35714.28)
        assert float(max_scales[0]) == pytest.approx(35714285.7)

        assert float(min_scales[1]) == pytest.approx(10000)
        assert float(max_scales[1]) == pytest.approx(1000000)

        assert float(min_scales[2]) == pytest.approx(1000)
        assert float(max_scales[2]) == pytest.approx(10000)

    def test_get_map_above_res(self, app):
        # no layer rendered
        resp = app.get(self.common_map_req)
        assert is_png(resp.body)
        assert is_transparent(resp.body)

    def test_get_map_mixed(self, app, cache_dir):
        # only res layer matches resolution range
        self.common_map_req.params["layers"] = "res,scale"
        self.common_map_req.params["bbox"] = "0,0,100000,100000"
        self.common_map_req.params["srs"] = "EPSG:900913"
        self.common_map_req.params.size = 100, 100
        with tmp_image((256, 256), format="jpeg") as img:
            expected_req = (
                {
                    "path": r"/service?LAYERs=reslayer&SERVICE=WMS&FORMAT=image%2Fjpeg"
                    "&REQUEST=GetMap&HEIGHT=256&SRS=EPSG%3A900913&styles="
                    "&VERSION=1.1.1&BBOX=0.0,0.0,156543.033928,156543.033928"
                    "&WIDTH=256"
                },
                {"body": img.read(), "headers": {"content-type": "image/png"}},
            )
            with mock_httpd(
                ("localhost", 42423), [expected_req], bbox_aware_query_comparator=True
            ):
                resp = app.get(self.common_map_req)
                assert is_png(resp.body)
                assert not is_transparent(resp.body)

        assert cache_dir.join(
            "res_cache_EPSG900913/08/000/000/128/000/000/128.jpeg"
        ).check()
