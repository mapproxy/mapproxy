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
Filter for tiles (watermark, pngquant, etc.)
"""

from mapproxy.image.message import ImageSource, WatermarkImage

import logging
log = logging.getLogger(__name__)

class TileFilter(object):
    """
    Tile filters can manipulate tiles before they are written to the cache.
    
    A TileFilter needs a ``create_filter`` method that takes ``layer_conf`` and a
    ``priority`` attribute.
    
    The priority controls in wich order the filters are applied. A higher value
    means that the filter is applied first.
    
    The ``create_filter`` method should return the filter function or ``None`` if
    the filter does not apply to the layer.
    Each filter should use some layer variable(s) to configure if the filter should
    apply to a specific layer. The ``create_filter`` should check for this
    variable(s) in the given ``layer_conf``. 
    
    The filter function gets a `mapproxy.core.cache._Tile` and must return the
    same (modified) tile.
    """
    priority = 50
    cache_conf_keys = []
    def create_filter(self, layer_conf):
        return NotImplementedError

def watermark_filter(text, opacity=None, spacing=None, font_size=None):
    """
    Returns a tile filter that adds a watermark to the tiles.
    :param text: watermark text
    """
    def _watermark_filter(tile):
        placement = tile_watermark_placement(tile.coord, spacing == 'wide')
        wimg = WatermarkImage(text, image_opts=tile.source.image_opts,
            placement=placement, opacity=opacity, font_size=font_size)
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

class WaterMarkTileFilter(TileFilter):
    """
    Adds a watermark to the tile. Uses the following layer configuration::
    
      watermark:
        text: 'Omniscale'
        opacity: 5
    
    """
    priority = 90
    cache_conf_keys = ['watermark']
    def create_filter(self, conf, context, **kw):
        if 'watermark' in conf:
            text = conf['watermark'].get('text', '')
            opacity = conf['watermark'].get('opacity')
            font_size = conf['watermark'].get('font_size')
            spacing = conf['watermark'].get('spacing')
            if spacing not in ('wide', None):
                raise ValueError('unsupported watermark spacing: %r' % spacing)
            if text != '':
                return watermark_filter(text, opacity=opacity, font_size=font_size,
                                        spacing=spacing)

class PNGQuantFilter(object):
    def __init__(self):
        self.enabled = False
        try:
            import osc.pngquant
            self.pngquant = osc.pngquant
            self.enabled = True
        except ImportError:
            log.warn('did not found pngquant module, disabled PNGQuantFilter')
        return None
    def __call__(self, tile):
        if not self.enabled or not self.pngquant.enabled:
            return tile
        tile_buf = tile.source_buffer(format='png')
        if tile_buf is None:
            return tile
        out_buf = self.pngquant.pngquant(tile_buf)
        tile.source = ImageSource(out_buf, format='png', size=tile.source.size)
        return tile

class PNGQuantTileFilter(TileFilter):
    """
    Filters the tile with pngquant tool. pngquant converts 24(32)bit RGB(A)
    images into 8bit colormap RGB(A) images. Reduces file size significant.
    
    Layer configuration::
    
      pngquant: True
    
    """
    priority = 10
    cache_conf_keys = ['pngquant']
    def create_filter(self, conf, context, **kw):
        if conf.get('pngquant', False):
            return PNGQuantFilter()