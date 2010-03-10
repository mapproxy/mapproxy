# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

"""
Filter for tiles (watermark, pngquant, etc.)
"""

from mapproxy.core.image import ImageSource, WatermarkImage

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
    def create_filter(self, layer_conf):
        return NotImplementedError

def watermark_filter(text, opacity=None):
    """
    Returns a tile filter that adds a watermark to the tiles.
    :param text: watermark text
    """
    def _watermark_filter(tile):
        odd = False if tile.coord[1] % 2 == 0 else True
        wimg = WatermarkImage(text, format=tile.source.format, odd=odd,
                              opacity=opacity)
        tile.source = wimg.draw(img=tile.source)
        return tile
    return _watermark_filter


class WaterMarkTileFilter(TileFilter):
    """
    Adds a watermark to the tile. Uses the following layer configuration::
    
      watermark:
        text: 'Omniscale'
        opacity: 5
    
    """
    priority = 90
    def create_filter(self, layer_conf):
        if 'watermark' in layer_conf.layer:
            text = layer_conf.layer['watermark'].get('text', '')
            opacity = layer_conf.layer['watermark'].get('opacity', None)
            if text != '':
                return watermark_filter(text, opacity=opacity)

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
    def create_filter(self, layer_conf):
        if layer_conf.layer.get('pngquant', False):
            return PNGQuantFilter()