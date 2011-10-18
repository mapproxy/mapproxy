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

"""
Filter for tiles (watermark, etc.)
"""

from mapproxy.image.message import WatermarkImage

def create_watermark_filter(conf, context, **kw):
    text = conf['watermark'].get('text', '')
    opacity = conf['watermark'].get('opacity')
    font_size = conf['watermark'].get('font_size')
    spacing = conf['watermark'].get('spacing')
    font_color = conf['watermark'].get('color')
    if spacing not in ('wide', None):
        raise ValueError('unsupported watermark spacing: %r' % spacing)
    if text != '':
        return watermark_filter(text, opacity=opacity, font_size=font_size,
                                spacing=spacing, font_color=font_color)

def watermark_filter(text, opacity=None, spacing=None, font_size=None, font_color=None):
    """
    Returns a tile filter that adds a watermark to the tiles.
    :param text: watermark text
    """
    def _watermark_filter(tile):
        placement = tile_watermark_placement(tile.coord, spacing == 'wide')
        wimg = WatermarkImage(text, image_opts=tile.source.image_opts,
            placement=placement, opacity=opacity, font_size=font_size,
            font_color=font_color)
        tile.source = wimg.draw(img=tile.source, in_place=False)
        return tile
    return _watermark_filter

def tile_watermark_placement(coord, double_spacing=False):
    if not double_spacing:
        if coord[1] % 2 == 0:
            return 'c'
        else:
            return 'b'
    
    if coord[1] % 2 != coord[0] % 2:
        return 'c'

    return None

