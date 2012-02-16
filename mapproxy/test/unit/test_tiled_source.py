from mapproxy.client.tile import TMSClient
from mapproxy.grid import TileGrid
from mapproxy.srs import SRS
from mapproxy.source.tile import TiledSource
from mapproxy.source.error import HTTPSourceErrorHandler
from mapproxy.layer import MapQuery

from mapproxy.test.http import mock_httpd
from nose.tools import eq_

TEST_SERVER_ADDRESS = ('127.0.0.1', 56413)
TESTSERVER_URL = 'http://%s:%d' % TEST_SERVER_ADDRESS

class TestTileClientOnError(object):
    def setup(self):
        self.grid = TileGrid(SRS(4326), bbox=[-180, -90, 180, 90])
        self.client = TMSClient(TESTSERVER_URL)

    def test_cacheable_response(self):
        error_handler = HTTPSourceErrorHandler()
        error_handler.add_handler(500, (255, 0, 0), cacheable=True)
        self.source = TiledSource(self.grid, self.client, error_handler=error_handler)

        with mock_httpd(TEST_SERVER_ADDRESS, [({'path': '/1/0/0.png'},
                                                {'body': 'error', 'status': 500, 'headers':{'content-type': 'text/plain'}})]):
            resp = self.source.get_map(MapQuery([-180, -90, 0, 90], (256, 256), SRS(4326), format='png'))
            assert resp.cacheable 
            eq_(resp.as_image().getcolors(), [((256*256), (255, 0, 0))])

    def test_image_response(self):
        error_handler = HTTPSourceErrorHandler()
        error_handler.add_handler(500, (255, 0, 0), cacheable=False)
        self.source = TiledSource(self.grid, self.client, error_handler=error_handler)

        with mock_httpd(TEST_SERVER_ADDRESS, [({'path': '/1/0/0.png'},
                                                {'body': 'error', 'status': 500, 'headers':{'content-type': 'text/plain'}})]):
            resp = self.source.get_map(MapQuery([-180, -90, 0, 90], (256, 256), SRS(4326), format='png'))
            assert not resp.cacheable 
            eq_(resp.as_image().getcolors(), [((256*256), (255, 0, 0))])

    def test_multiple_image_responses(self):
        error_handler = HTTPSourceErrorHandler()
        error_handler.add_handler(500, (255, 0, 0), cacheable=False)
        error_handler.add_handler(204, (255, 0, 127, 200), cacheable=True)
        self.source = TiledSource(self.grid, self.client, error_handler=error_handler)

        with mock_httpd(TEST_SERVER_ADDRESS, [
            ({'path': '/1/0/0.png'}, {'body': 'error', 'status': 500, 'headers':{'content-type': 'text/plain'}}),
            ({'path': '/1/0/0.png'}, {'body': 'error', 'status': 204, 'headers':{'content-type': 'text/plain'}})]):

            resp = self.source.get_map(MapQuery([-180, -90, 0, 90], (256, 256), SRS(4326), format='png'))
            assert not resp.cacheable 
            eq_(resp.as_image().getcolors(), [((256*256), (255, 0, 0))])

            resp = self.source.get_map(MapQuery([-180, -90, 0, 90], (256, 256), SRS(4326), format='png'))
            assert resp.cacheable 
            eq_(resp.as_image().getcolors(), [((256*256), (255, 0, 127, 200))])
