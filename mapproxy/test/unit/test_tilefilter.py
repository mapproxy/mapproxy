# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
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

from mapproxy.tilefilter import tile_watermark_placement


def test_tile_watermark_placement():
    assert tile_watermark_placement((0, 0, 0)) == "c"
    assert tile_watermark_placement((1, 0, 0)) == "c"
    assert tile_watermark_placement((0, 1, 0)) == "b"
    assert tile_watermark_placement((1, 1, 0)) == "b"

    assert tile_watermark_placement((0, 0, 0), True) == None
    assert tile_watermark_placement((1, 0, 0), True) == "c"
    assert tile_watermark_placement((2, 0, 0), True) == None

    assert tile_watermark_placement((0, 1, 0), True) == "c"
    assert tile_watermark_placement((1, 1, 0), True) == None
    assert tile_watermark_placement((2, 1, 0), True) == "c"
