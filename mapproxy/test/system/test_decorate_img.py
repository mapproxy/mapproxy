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

from mapproxy.test.system import module_setup, module_teardown, SystemTest, make_base_config
from mapproxy.test.image import is_png
from mapproxy.request.wms import WMS111MapRequest
from cStringIO import StringIO

from mapproxy.platform.image import Image
from mapproxy.image import ImageSource
from nose.tools import eq_

test_config = {}
base_config = make_base_config(test_config)


def setup_module():
    module_setup(test_config, 'layer.yaml', with_cache_data=True)


def teardown_module():
    module_teardown(test_config)


def to_greyscale(img_src):
    img = img_src.as_image()
    if img_src.image_opts.transparent:
        img = img.convert('LA').convert('RGBA')
    else:
        img = img.convert('L').convert('RGB')
    return ImageSource(img, img_src.image_opts)


class TestDecorateImg(SystemTest):
    config = test_config

    def test_wms(self):
        req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap'))
        resp = self.app.get(req, extra_environ={'mapproxy.decorate_img': to_greyscale})
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')

    def test_wms_transparent(self):
        req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache_transparent', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap', transparent='True'))
        resp = self.app.get(req, extra_environ={'mapproxy.decorate_img': to_greyscale})
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGBA')

    def test_wms_bgcolor(self):
        req = WMS111MapRequest(url='/service?', param=dict(service='WMS',
             version='1.1.1', bbox='-180,0,0,80', width='200', height='200',
             layers='wms_cache_transparent', srs='EPSG:4326', format='image/png',
             styles='', request='GetMap', bgcolor='0xff00a0'))
        resp = self.app.get(req, extra_environ={'mapproxy.decorate_img': to_greyscale})
        data = StringIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        eq_(img.mode, 'RGB')
        eq_(sorted(img.getcolors())[-1][1], (94, 94, 94))
