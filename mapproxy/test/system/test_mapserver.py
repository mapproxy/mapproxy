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

import os
import sys
import stat
import shutil

from io import BytesIO

import pytest

from mapproxy.request.wms import WMS111MapRequest
from mapproxy.compat.image import Image
from mapproxy.test.image import is_png
from mapproxy.test.system import SysTest


pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="CGI tests not ported for Windows"
)


@pytest.fixture(scope="module")
def config_file():
    return "mapserver.yaml"


class TestMapServerCGI(SysTest):

    @pytest.fixture(scope="class")
    def additional_files(self, base_dir):
        shutil.copy(
            os.path.join(os.path.dirname(__file__), "fixture", "minimal_cgi.py"),
            base_dir.strpath,
        )

        os.chmod(
            base_dir.join("minimal_cgi.py").strpath, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR
        )

        base_dir.join("tmp").mkdir()

    def setup(self):
        self.common_map_req = WMS111MapRequest(
            url="/service?",
            param=dict(
                service="WMS",
                version="1.1.1",
                bbox="-180,0,0,80",
                width="200",
                height="200",
                layers="ms",
                srs="EPSG:4326",
                format="image/png",
                styles="",
                request="GetMap",
            ),
        )

    def test_get_map(self, app):
        resp = app.get(self.common_map_req)
        assert resp.content_type == "image/png"
        data = BytesIO(resp.body)
        assert is_png(data)
        img = Image.open(data)
        img = img.convert("RGB")
        assert img.getcolors() == [(200 * 200, (255, 0, 0))]
