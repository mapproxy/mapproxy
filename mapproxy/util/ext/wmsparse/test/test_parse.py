import os

from ..parse import parse_capabilities

from nose.tools import eq_

def local_filename(filename):
    return os.path.join(os.path.dirname(__file__), filename)


class TestWMS111(object):
    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename('wms-omniscale-111.xml'))
        md = cap.metadata()
        eq_(md['name'], 'OGC:WMS')
        eq_(md['title'], 'Omniscale OpenStreetMap WMS')
        eq_(md['access_constraints'], 'Here be dragons.')
        eq_(md['fees'], 'none')
        eq_(md['online_resource'], 'http://omniscale.de/')
        eq_(md['abstract'], 'Omniscale OpenStreetMap WMS (powered by MapProxy)')


        eq_(md['contact']['person'], 'Oliver Tonnhofer')
        eq_(md['contact']['organization'], 'Omniscale')
        eq_(md['contact']['position'], 'Technical Director')
        eq_(md['contact']['address'], 'Nadorster Str. 60')
        eq_(md['contact']['city'], 'Oldenburg')
        eq_(md['contact']['postcode'], '26123')
        eq_(md['contact']['country'], 'Germany')
        eq_(md['contact']['phone'], '+49(0)441-9392774-0')
        eq_(md['contact']['fax'], '+49(0)441-9392774-9')
        eq_(md['contact']['email'], 'osm@omniscale.de')


    def test_parse_layer(self):
        cap = parse_capabilities(local_filename('wms-omniscale-111.xml'))
        lyrs = cap.layers_list()
        eq_(len(lyrs), 2)
        eq_(lyrs[0]['llbbox'], [-180.0, -85.0511287798, 180.0, 85.0511287798])
        eq_(lyrs[0]['srs'],
            set(['EPSG:4326', 'EPSG:4258', 'CRS:84', 'EPSG:900913', 'EPSG:31466',
                'EPSG:31467', 'EPSG:31468', 'EPSG:25831', 'EPSG:25832',
                'EPSG:25833', 'EPSG:3857',
            ])
        )
        eq_(len(lyrs[0]['bbox_srs']), 1)
        eq_(lyrs[0]['bbox_srs']['EPSG:4326'], [-180.0, -85.0511287798, 180.0, 85.0511287798])


    def test_parse_layer_2(self):
        cap = parse_capabilities(local_filename('wms-large-111.xml'))
        lyrs = cap.layers_list()
        eq_(len(lyrs), 46)
        eq_(lyrs[0]['llbbox'], [-10.4, 35.7, 43.0, 74.1])
        eq_(lyrs[0]['srs'],
            set(['EPSG:31467', 'EPSG:31466', 'EPSG:31465', 'EPSG:31464',
                'EPSG:31463', 'EPSG:31462', 'EPSG:4326', 'EPSG:31469', 'EPSG:31468',
                'EPSG:31257', 'EPSG:31287', 'EPSG:31286', 'EPSG:31285', 'EPSG:31284',
                'EPSG:31258', 'EPSG:31259', 'EPSG:31492', 'EPSG:31493', 'EPSG:25833',
                'EPSG:25832', 'EPSG:31494', 'EPSG:31495', 'EPSG:28992',
            ])
        )
        eq_(lyrs[1]['name'], 'Grenzen')
        eq_(lyrs[1]['legend']['url'],
            "http://example.org/service?SERVICE=WMS&version=1.1.1&service=WMS&request=GetLegendGraphic&layer=Grenzen&format=image/png&STYLE=default"
        )

class TestWMS130(object):
    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename('wms-omniscale-130.xml'))
        md = cap.metadata()
        eq_(md['name'], 'WMS')
        eq_(md['title'], 'Omniscale OpenStreetMap WMS')

        req = cap.requests()
        eq_(req['GetMap'], 'http://osm.omniscale.net/proxy/service?')

    def test_parse_layer(self):
        cap = parse_capabilities(local_filename('wms-omniscale-130.xml'))
        lyrs = cap.layers_list()
        eq_(len(lyrs), 2)
        eq_(lyrs[0]['llbbox'], [-180.0, -85.0511287798, 180.0, 85.0511287798])
        eq_(lyrs[0]['srs'],
            set(['EPSG:4326', 'EPSG:4258', 'CRS:84', 'EPSG:900913', 'EPSG:31466',
                'EPSG:31467', 'EPSG:31468', 'EPSG:25831', 'EPSG:25832',
                'EPSG:25833', 'EPSG:3857',
            ])
        )
        eq_(len(lyrs[0]['bbox_srs']), 4)
        eq_(set(lyrs[0]['bbox_srs'].keys()), set(['CRS:84', 'EPSG:900913', 'EPSG:4326', 'EPSG:3857']))
        eq_(lyrs[0]['bbox_srs']['EPSG:3857'], [-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428])
        # EPSG:4326 bbox should be switched to long/lat
        eq_(lyrs[0]['bbox_srs']['EPSG:4326'], (-180.0, -85.0511287798, 180.0, 85.0511287798))


class TestLargeWMSCapabilities(object):
    def test_parse_metadata(self):
        cap = parse_capabilities(local_filename('wms_nasa_cap.xml'))
        md = cap.metadata()
        eq_(md['name'], 'OGC:WMS')
        eq_(md['title'], 'JPL Global Imagery Service')

    def test_parse_layer(self):
        cap = parse_capabilities(local_filename('wms_nasa_cap.xml'))
        lyrs = cap.layers_list()
        eq_(len(lyrs), 15)
        eq_(len(lyrs[0]['bbox_srs']), 0)
