import os
from mapproxy.core.config import base_config
from mapproxy.core import srs

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
        