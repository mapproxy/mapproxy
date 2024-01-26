import os

from ..parse import parse_capabilities


def local_filename(filename):
    return os.path.join(os.path.dirname(__file__), filename)


class TestWMS111(object):

    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename("wms-example-111.xml"))
        md = cap.metadata()
        assert md["name"] == "OGC:WMS"
        assert md["title"] == "ACME OpenStreetMap WMS"
        assert md["access_constraints"] == "Here be dragons."
        assert md["fees"] == "none"
        assert md["online_resource"] == "http://example.org/"
        assert md["abstract"] == "ACME OpenStreetMap WMS (powered by MapProxy)"

        assert md["contact"]["person"] == "Bob Mustermann"
        assert md["contact"]["organization"] == "ACME"
        assert md["contact"]["position"] == "Technical Director"
        assert md["contact"]["address"] == "Fakestreet 123"
        assert md["contact"]["city"] == "Fakecity"
        assert md["contact"]["postcode"] == "12345"
        assert md["contact"]["country"] == "Germany"
        assert md["contact"]["phone"] == "0123456789"
        assert md["contact"]["fax"] == "0123456789"
        assert md["contact"]["email"] == "info@example.org"

    def test_parse_layer(self):
        cap = parse_capabilities(local_filename("wms-example-111.xml"))
        lyrs = cap.layers_list()
        assert len(lyrs) == 2
        assert lyrs[0]["llbbox"] == [-180.0, -85.0511287798, 180.0, 85.0511287798]
        assert lyrs[0]["srs"] == {"EPSG:4326", "EPSG:4258", "CRS:84", "EPSG:900913", "EPSG:31466", "EPSG:31467",
                                  "EPSG:31468", "EPSG:25831", "EPSG:25832", "EPSG:25833", "EPSG:3857"}
        assert len(lyrs[0]["bbox_srs"]) == 1
        assert lyrs[0]["bbox_srs"]["EPSG:4326"] == [
            -180.0,
            -85.0511287798,
            180.0,
            85.0511287798,
        ]

    def test_parse_layer_2(self):
        cap = parse_capabilities(local_filename("wms-large-111.xml"))
        lyrs = cap.layers_list()
        assert len(lyrs) == 46
        assert lyrs[0]["llbbox"] == [-10.4, 35.7, 43.0, 74.1]
        assert lyrs[0]["srs"] == {"EPSG:31467", "EPSG:31466", "EPSG:31465", "EPSG:31464", "EPSG:31463", "EPSG:31462",
                                  "EPSG:4326", "EPSG:31469", "EPSG:31468", "EPSG:31257", "EPSG:31287", "EPSG:31286",
                                  "EPSG:31285", "EPSG:31284", "EPSG:31258", "EPSG:31259", "EPSG:31492", "EPSG:31493",
                                  "EPSG:25833", "EPSG:25832", "EPSG:31494", "EPSG:31495", "EPSG:28992"}
        assert lyrs[1]["name"] == "Grenzen"
        assert (
            lyrs[1]["legend"]["url"]
            == "http://example.org/service?SERVICE=WMS&version=1.1.1&service=WMS&request=GetLegendGraphic&layer=Grenzen&format=image/png&STYLE=default"  # noqa
        )


class TestWMS130(object):

    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename("wms-example-130.xml"))
        md = cap.metadata()
        assert md["name"] == "WMS"
        assert md["title"] == "ACME OpenStreetMap WMS"

        req = cap.requests()
        assert req["GetMap"] == "http://example.org/service"

    def test_parse_layer(self):
        cap = parse_capabilities(local_filename("wms-example-130.xml"))
        lyrs = cap.layers_list()
        assert len(lyrs) == 2
        assert lyrs[0]["llbbox"] == [-180.0, -85.0511287798, 180.0, 85.0511287798]
        assert lyrs[0]["srs"] == {"EPSG:4326", "EPSG:4258", "CRS:84", "EPSG:900913", "EPSG:31466", "EPSG:31467",
                                  "EPSG:31468", "EPSG:25831", "EPSG:25832", "EPSG:25833", "EPSG:3857"}
        assert len(lyrs[0]["bbox_srs"]) == 4
        assert set(lyrs[0]["bbox_srs"].keys()) == {"CRS:84", "EPSG:900913", "EPSG:4326", "EPSG:3857"}
        assert lyrs[0]["bbox_srs"]["EPSG:3857"] == [
            -20037508.3428,
            -20037508.3428,
            20037508.3428,
            20037508.3428,
        ]
        # EPSG:4326 bbox should be switched to long/lat
        assert lyrs[0]["bbox_srs"]["EPSG:4326"] == (
            -180.0,
            -85.0511287798,
            180.0,
            85.0511287798,
        )


class TestLargeWMSCapabilities(object):

    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename("wms_nasa_cap.xml"))
        md = cap.metadata()
        assert md["name"] == "OGC:WMS"
        assert md["title"] == "JPL Global Imagery Service"

    def test_parse_layer(self):
        cap = parse_capabilities(local_filename("wms_nasa_cap.xml"))
        lyrs = cap.layers_list()
        assert len(lyrs) == 15
        assert len(lyrs[0]["bbox_srs"]) == 0
