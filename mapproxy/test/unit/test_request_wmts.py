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

from mapproxy.exception import RequestError
from mapproxy.request.wmts import wmts_request, WMTS100CapabilitiesRequest
from mapproxy.request.wmts import (
    URLTemplateConverter,
    FeatureInfoURLTemplateConverter,
    InvalidWMTSTemplate,
    make_wmts_rest_request_parser,
    WMTS100RestTileRequest,
    WMTS100RestFeatureInfoRequest,
)
from mapproxy.request.base import url_decode

import pytest


def dummy_req(args):
    return DummyRequest(url_decode(args.replace("\n", "")))


def dummy_rest_req(path):
    return DummyRequest(args="", path=path)


class DummyRequest(object):

    def __init__(self, args, path="", url=""):
        self.args = args
        self.path = path
        self.base_url = url


def test_tile_request():
    args = """requeST=GetTile&service=wmts&tileMatrixset=EPSG900913&
tilematrix=2&tileROW=4&TILECOL=2&FORMAT=image/png&Style=&layer=Foo&version=1.0.0"""
    req = wmts_request(dummy_req(args))

    assert req.params.coord == (2, 4, "2")
    assert req.params.layer == "Foo"
    assert req.params.format == "png"
    assert req.params.tilematrixset == "EPSG900913"


def test_featureinfo_request():
    args = """requeST=GetFeatureInfo&service=wmts&tileMatrixset=EPSG900913&
tilematrix=2&tileROW=4&TILECOL=2&FORMAT=image/png&Style=&layer=Foo&version=1.0.0&
i=5&j=10&infoformat=application/json"""
    req = wmts_request(dummy_req(args))

    assert req.params.coord == (2, 4, "2")
    assert req.params.layer == "Foo"
    assert req.params.format == "png"
    assert req.params.tilematrixset == "EPSG900913"
    assert req.params.pos == (5, 10)
    assert req.params.infoformat == "application/json"


def test_capabilities_request():
    args = """requeST=GetCapabilities&service=wmts"""
    req = wmts_request(dummy_req(args))

    assert isinstance(req, WMTS100CapabilitiesRequest)


def test_template_converter():
    regexp = URLTemplateConverter(
        "/{Layer}/{Style}/{TileMatrixSet}-{TileMatrix}-{TileCol}-{TileRow}/tile"
    ).regexp()
    match = regexp.match("/wmts/test/bar/foo-EPSG4326-4-12-99/tile")
    assert match
    assert match.groupdict()["Layer"] == "test"
    assert match.groupdict()["TileMatrixSet"] == "foo-EPSG4326"
    assert match.groupdict()["TileMatrix"] == "4"
    assert match.groupdict()["TileCol"] == "12"
    assert match.groupdict()["TileRow"] == "99"
    assert match.groupdict()["Style"] == "bar"


def test_template_converter_deprecated_format():
    # old format that doesn't match the WMTS spec, now deprecated
    regexp = URLTemplateConverter(
        "/{{Layer}}/{{Style}}/{{TileMatrixSet}}-{{TileMatrix}}-{{TileCol}}-{{TileRow}}/tile"
    ).regexp()
    match = regexp.match("/wmts/test/bar/foo-EPSG4326-4-12-99/tile")
    assert match
    assert match.groupdict()["Layer"] == "test"
    assert match.groupdict()["TileMatrixSet"] == "foo-EPSG4326"
    assert match.groupdict()["TileMatrix"] == "4"
    assert match.groupdict()["TileCol"] == "12"
    assert match.groupdict()["TileRow"] == "99"
    assert match.groupdict()["Style"] == "bar"


def test_template_converter_missing_vars():
    with pytest.raises(InvalidWMTSTemplate):
        URLTemplateConverter("/wmts/{Style}/{TileMatrixSet}/{TileCol}.png").regexp()


def test_template_converter_dimensions():
    converter = URLTemplateConverter(
        "/{Layer}/{Dim1}/{Dim2}/{TileMatrixSet}-{TileMatrix}-{TileCol}-{TileRow}/tile"
    )
    assert converter.dimensions == ["Dim1", "Dim2"]


class TestRestRequestParser(object):

    @pytest.fixture
    def parser(self):
        return make_wmts_rest_request_parser(
            URLTemplateConverter(
                "/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.{Format}"
            ),
            FeatureInfoURLTemplateConverter(
                "/{Layer}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}/{I}/{J}.{InfoFormat}"
            ),
        )

    @pytest.mark.parametrize(
        "url,tile,pos",
        [
            ["/wmts/roads/webmercator/09/201/123/10/30.json", (201, 123, 9), (10, 30)],
            ["/wmts/roads/webmercator/10/201/1/0/999.json", (201, 1, 10), (0, 999)],
            ["/wmts/roads/webmercator/09/201/123/10/30json", None, None],
            ["/wmts/roads/webmercator/09/201/123/10.json", None, None],
            ["/wmts/roads-webmercator/09/201/123/10/30.json", None, None],
            ["/roads/webmercator/09/201/123/10/30.json", None, None],
        ],
    )
    def test_featureinfo(self, parser, url, tile, pos):
        if tile is None:
            with pytest.raises(RequestError):
                parser(dummy_rest_req(url))
        else:
            req = parser(dummy_rest_req(url))
            assert isinstance(req, WMTS100RestFeatureInfoRequest)
            req.make_request()
            assert req.pos == pos
            assert req.tile == tile
            assert req.infoformat == "json"
            assert req.tilematrixset == "webmercator"

    @pytest.mark.parametrize(
        "url,tile",
        [
            ["/wmts/roads/webmercator/09/201/123.png", (201, 123, 9)],
            ["/wmts/roads/webmercator/10/201/123.png", (201, 123, 10)],
            ["/wmts/roads/webmercator/10/201/123a.png", None],
            ["/wmts/roads/webmercator/10/201/123png", None],
            ["/wmts/roads/webmercator/10/2013.png", None],
            ["/wmts/roads-webmercator/10/201/123.png", None],
        ],
    )
    def test_tile(self, parser, url, tile):
        if tile is None:
            with pytest.raises(RequestError):
                parser(dummy_rest_req(url))
        else:
            req = parser(dummy_rest_req(url))
            assert isinstance(req, WMTS100RestTileRequest)
            req.make_request()
            assert req.tile == tile
            assert req.format == "png"
            assert req.tilematrixset == "webmercator"
