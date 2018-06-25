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

from __future__ import division

from io import BytesIO

import pytest

from mapproxy.compat.image import Image
from mapproxy.test.system import SysTest


has_mapnik = True
try:
    import mapnik
except ImportError:
    try:
        import mapnik2 as mapnik
    except ImportError:
        has_mapnik = False


mapnik_xml = (
    b"""
<?xml version="1.0"?>
<!DOCTYPE Map>
<Map background-color="#ff0000" bgcolor="#ff0000" srs="+proj=latlong +datum=WGS84">
    <Layer name="marker">
        <StyleName>marker</StyleName>
        <Datasource>
            <Parameter name="type">ogr</Parameter>
            <Parameter name="file">test_point.geojson</Parameter>
            <Parameter name="layer">OGRGeoJSON</Parameter>
        </Datasource>
    </Layer>
    <Style name="marker">
        <Rule>
            <MarkersSymbolizer fill="transparent" width="10" height="10" stroke="black" stroke-width="3" placement="point" marker-type="ellipse"/>
        </Rule>
    </Style>
</Map>
""".strip()
)

test_point_geojson = (
    b"""
{"type": "Feature", "geometry": {"type": "Point", "coordinates": [-45, -45]}, "properties": {}}
""".strip()
)

mapnik_transp_xml = (
    b"""
<?xml version="1.0"?>
<!DOCTYPE Map>
<Map background-color="transparent" srs="+proj=latlong +datum=WGS84">
</Map>
""".strip()
)


@pytest.fixture(scope="module")
def config_file():
    return "mapnik_source.yaml"


@pytest.fixture(scope="module")
def additional_files(base_dir):
    base_dir.join("test_point.geojson").write_binary(test_point_geojson)
    base_dir.join("mapnik.xml").write_binary(mapnik_xml)
    base_dir.join("mapnik-transparent.xml").write_binary(mapnik_transp_xml)


@pytest.mark.skipif(not has_mapnik, reason="requires mapnik")
class TestMapnikSource(SysTest):

    def test_get_map(self, app):
        req = (
            r"/service?LAYERs=mapnik&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326"
            "&VERSION=1.1.1&BBOX=-90,-90,0,0&styles="
            "&WIDTH=200&"
        )

        resp = app.get(req)
        data = BytesIO(resp.body)
        img = Image.open(data)
        colors = sorted(img.getcolors(), reverse=True)
        # map bg color + black marker
        assert 39700 < colors[0][0] < 39900, colors[0][0]
        assert colors[0][1] == (255, 0, 0, 255)
        assert 50 < colors[1][0] < 150, colors[1][0]
        assert colors[1][1] == (0, 0, 0, 255)

    def test_get_map_hq(self, app):
        req = (
            r"/service?LAYERs=mapnik_hq&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326"
            "&VERSION=1.1.1&BBOX=-90,-90,0,0&styles="
            "&WIDTH=200&"
        )

        resp = app.get(req)
        data = BytesIO(resp.body)
        img = Image.open(data)
        colors = sorted(img.getcolors(), reverse=True)
        # map bg color + black marker (like above, but marker is scaled up)
        assert 39500 < colors[0][0] < 39600, colors[0][0]
        assert colors[0][1] == (255, 0, 0, 255)
        assert 250 < colors[1][0] < 350, colors[1][0]
        assert colors[1][1] == (0, 0, 0, 255)

    def test_get_map_outside_coverage(self, app):
        req = (
            r"/service?LAYERs=mapnik&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326"
            "&VERSION=1.1.1&BBOX=-175,-85,-172,-82&styles="
            "&WIDTH=200&&BGCOLOR=0x00ff00"
        )

        resp = app.get(req)
        data = BytesIO(resp.body)
        img = Image.open(data)
        colors = sorted(img.getcolors(), reverse=True)
        # wms request bg color
        assert colors[0] == (40000, (0, 255, 0))

    def test_get_map_unknown_file(self, app):
        req = (
            r"/service?LAYERs=mapnik_unknown&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326"
            "&VERSION=1.1.1&BBOX=-90,-90,0,0&styles="
            "&WIDTH=200&&BGCOLOR=0x00ff00"
        )

        resp = app.get(req)
        assert "unknown.xml" in resp.body, resp.body

    def test_get_map_transparent(self, app):
        req = (
            r"/service?LAYERs=mapnik_transparent&SERVICE=WMS&FORMAT=image%2Fpng"
            "&REQUEST=GetMap&HEIGHT=200&SRS=EPSG%3A4326"
            "&VERSION=1.1.1&BBOX=-90,-90,0,0&styles="
            "&WIDTH=200&transparent=True"
        )

        resp = app.get(req)
        data = BytesIO(resp.body)
        img = Image.open(data)
        colors = sorted(img.getcolors(), reverse=True)
        assert colors[0] == (40000, (0, 0, 0, 0))
