# This file is part of the MapProxy project.
# Copyright (C) 2010,2012 Omniscale <http://omniscale.de>
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
Image and tile manipulation (transforming, merging, etc).
"""
from __future__ import with_statement

from mapproxy.platform.image import Image, ImageColor
from mapproxy.image import BlankImageSource, ImageSource
from mapproxy.image.opts import create_image, ImageOptions
from mapproxy.image.mask import mask_image

import logging
log = logging.getLogger('mapproxy.image')

class LayerMerger(object):
    """
    Merge multiple layers into one image.
    """
    def __init__(self):
        self.layers = []
        self.cacheable = True

    def add(self, layer_img, layer=None):
        """
        Add one layer image to merge. Bottom-layers first.
        """
        if layer_img is not None:
            self.layers.append((layer_img, layer))

    def merge(self, image_opts, size=None, bbox=None, bbox_srs=None, coverage=None):
        """
        Merge the layers. If the format is not 'png' just return the last image.
        
        :param format: The image format for the result.
        :param size: The size for the merged output.
        :rtype: `ImageSource`
        """
        if not self.layers:
            return BlankImageSource(size=size, image_opts=image_opts, cacheable=True)
        if len(self.layers) == 1:
            layer_img, layer = self.layers[0]
            layer_opts = layer_img.image_opts
            if (((layer_opts and not layer_opts.transparent) or image_opts.transparent) 
                and (not size or size == layer_img.size)
                and (not layer or not layer.coverage or not layer.coverage.clip)):
                # layer is opaque, no need to make transparent or add bgcolor
                return layer_img
        
        if size is None:
            size = self.layers[0][0].size
        
        cacheable = self.cacheable
        result = create_image(size, image_opts)

        for layer_img, layer in self.layers:
            if not layer_img.cacheable:
                cacheable = False
            img = layer_img.as_image()
            layer_image_opts = layer_img.image_opts
            
            if layer and layer.coverage and layer.coverage.clip:
                img = mask_image(img, bbox, bbox_srs, layer.coverage)
                
            if (layer_image_opts and layer_image_opts.opacity is not None
                and layer_image_opts.opacity < 1.0):
                img = img.convert(result.mode)
                result = Image.blend(result, img, layer_image_opts.opacity)
            else:
                if img.mode == 'RGBA':
                    # paste w transparency mask from layer
                    result.paste(img, (0, 0), img)
                else:
                    result.paste(img, (0, 0))
        
        # apply global clip coverage
        if coverage:
            bg = create_image(size, image_opts)
            mask = mask_image(result, bbox, bbox_srs, coverage)
            bg.paste(result, (0, 0), mask)
            result = bg

        return ImageSource(result, size=size, image_opts=image_opts, cacheable=cacheable)

def merge_images(images, image_opts, size=None):
    """
    Merge multiple images into one.
    
    :param images: list of `ImageSource`, bottom image first
    :param format: the format of the output `ImageSource`
    :param size: size of the merged image, if ``None`` the size
                 of the first image is used
    :rtype: `ImageSource`
    """
    merger = LayerMerger()
    for img in images:
        merger.add(img)
    return merger.merge(image_opts=image_opts, size=size)

def concat_legends(legends, format='png', size=None, bgcolor='#ffffff', transparent=True):
    """
    Merge multiple legends into one
    :param images: list of `ImageSource`, bottom image first
    :param format: the format of the output `ImageSource`
    :param size: size of the merged image, if ``None`` the size
                 will be calculated
    :rtype: `ImageSource`
    """
    if not legends:
        return BlankImageSource(size=(1,1), image_opts=ImageOptions(bgcolor=bgcolor, transparent=transparent))
    if len(legends) == 1:
        return legends[0]
    
    legends = legends[:]
    legends.reverse()
    if size is None:
        legend_width = 0
        legend_height = 0
        legend_position_y = []
        #iterate through all legends, last to first, calc img size and remember the y-position
        for legend in legends:
            legend_position_y.append(legend_height)
            tmp_img = legend.as_image()
            legend_width = max(legend_width, tmp_img.size[0])
            legend_height += tmp_img.size[1] #images shall not overlap themselfs
            
        size = [legend_width, legend_height]
    bgcolor = ImageColor.getrgb(bgcolor)
    
    if transparent:
        img = Image.new('RGBA', size, bgcolor+(0,))
    else:
        img = Image.new('RGB', size, bgcolor)
    for i in range(len(legends)):
        legend_img = legends[i].as_image()
        if legend_img.mode == 'RGBA':
            # paste w transparency mask from layer
            img.paste(legend_img, (0, legend_position_y[i]), legend_img)
        else:
            img.paste(legend_img, (0, legend_position_y[i]))
    return ImageSource(img, image_opts=ImageOptions(format=format))
