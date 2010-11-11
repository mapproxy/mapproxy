import os
from mapproxy.config import base_config
from mapproxy import srs
from mapproxy.srs import SRS

class Test_0_ProjDefaultDataPath(object):
    
    def test_known_srs(self):
        s = srs.SRS(4326)
    
    def test_unknown_srs(self):
        try:
            srs.SRS(1234)
        except RuntimeError:
            pass
        else:
            assert False, 'RuntimeError expected'
        

class Test_1_ProjDataPath(object):
    
    def setup(self):
        srs._proj_initalized = False
        srs._srs_cache = {}
        base_config().srs.proj_data_dir = os.path.dirname(__file__)
    
    def test_dummy_srs(self):
        s = srs.SRS(1234)
    
    def test_unknown_srs(self):
        try:
            srs.SRS(2339)
        except RuntimeError:
            pass
        else:
            assert False, 'RuntimeError expected'
    
    def teardown(self):
        srs._proj_initalized = False
        srs._srs_cache = {}
        base_config().srs.proj_data_dir = None


class TestSRS(object):
    def test_epsg4326(self):
        srs = SRS(4326)
        
        assert srs.is_latlong
        assert not srs.is_axis_order_en
        assert srs.is_axis_order_ne
        
    def test_crs84(self):
        srs = SRS('CRS:84')
        
        assert srs.is_latlong
        assert srs.is_axis_order_en
        assert not srs.is_axis_order_ne

        assert srs == SRS('EPSG:4326')

    def test_epsg31467(self):
        srs = SRS('EPSG:31467')
        
        assert not srs.is_latlong
        assert not srs.is_axis_order_en
        assert srs.is_axis_order_ne

    def test_epsg900913(self):
        srs = SRS('epsg:900913')
        
        assert not srs.is_latlong
        assert srs.is_axis_order_en
        assert not srs.is_axis_order_ne

    def test_from_srs(self):
        srs1 = SRS('epgs:4326')
        srs2 = SRS(srs1)
        assert srs1 == srs2
        