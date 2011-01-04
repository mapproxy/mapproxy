# This file is part of the MapProxy project.
# Copyright (C) 2010, 2011 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mapproxy.tilefilter import tile_watermark_placement
def test_tile_watermark_placement():
    from nose.tools import eq_
    eq_(tile_watermark_placement((0, 0, 0)), 'c')
    eq_(tile_watermark_placement((1, 0, 0)), 'c')
    eq_(tile_watermark_placement((0, 1, 0)), 'b')
    eq_(tile_watermark_placement((1, 1, 0)), 'b')
    
    eq_(tile_watermark_placement((0, 0, 0), True), None)
    eq_(tile_watermark_placement((1, 0, 0), True), 'c')
    eq_(tile_watermark_placement((2, 0, 0), True), None)

    eq_(tile_watermark_placement((0, 1, 0), True), 'c')
    eq_(tile_watermark_placement((1, 1, 0), True), None)
    eq_(tile_watermark_placement((2, 1, 0), True), 'c')
