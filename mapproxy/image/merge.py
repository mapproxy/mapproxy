# This file is part of the MapProxy project.
# Copyright (C) 2010-2016 Omniscale <http://omniscale.de>
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

from collections import namedtuple
from mapproxy.compat.image import Image, ImageColor, ImageChops, ImageMath
from mapproxy.compat.image import has_alpha_composite_support
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

    def add(self, img, coverage=None):
        """
        Add one layer image to merge. Bottom-layers first.
        """
        if img is not None:
            self.layers.append((img, coverage))


class LayerMerger(LayerMerger):

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
            layer_img, layer_coverage = self.layers[0]
            layer_opts = layer_img.image_opts
            if (((layer_opts and not layer_opts.transparent) or image_opts.transparent)
                and (not size or size == layer_img.size)
                and (not layer_coverage or not layer_coverage.clip)
                and not coverage):
                # layer is opaque, no need to make transparent or add bgcolor
                return layer_img

        if size is None:
            size = self.layers[0][0].size

        cacheable = self.cacheable
        result = create_image(size, image_opts)
        for layer_img, layer_coverage in self.layers:
            if not layer_img.cacheable:
                cacheable = False
            img = layer_img.as_image()
            layer_image_opts = layer_img.image_opts
            if layer_image_opts is None:
                opacity = None
            else:
                opacity = layer_image_opts.opacity

            if layer_coverage and layer_coverage.clip:
                img = mask_image(img, bbox, bbox_srs, layer_coverage)

            if result.mode != 'RGBA':
                merge_composite = False
            else:
                merge_composite = has_alpha_composite_support()

            if 'transparency' in img.info:
                # non-paletted PNGs can have a fixed transparency value
                # convert to RGBA to have full alpha
                img = img.convert('RGBA')

            if merge_composite:
                if opacity is not None and opacity < 1.0:
                    # fade-out img to add opacity value
                    img = img.convert("RGBA")
                    alpha = img.split()[3]
                    alpha = ImageChops.multiply(
                        alpha,
                        ImageChops.constant(alpha, int(255 * opacity))
                    )
                    img.putalpha(alpha)
                if img.mode in ('RGBA', 'P'):
                    # assume paletted images have transparency
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    result = Image.alpha_composite(result, img)
                else:
                    result.paste(img, (0, 0))
            else:
                if opacity is not None and opacity < 1.0:
                    img = img.convert(result.mode)
                    result = Image.blend(result, img, layer_image_opts.opacity)
                elif img.mode in ('RGBA', 'P'):
                    # assume paletted images have transparency
                    if img.mode == 'P':
                        img = img.convert('RGBA')
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


band_ops = namedtuple("band_ops", ["dst_band", "src_img", "src_band", "factor"])

class BandMerger(object):
    """
    Merge bands from multiple sources into one image.

       sources:
           r: [{source: nir_cache, band: 0, factor: 0.4}, {source: dop_cache, band: 0, factor: 0.6}]
           g: [{source: dop_cache, band: 2}]
           b: [{source: dop_cache, band: 1}]

       sources:
           l: [
               {source: dop_cache, band: 0, factor: 0.6},
               {source: dop_cache, band: 1, factor: 0.3},
               {source: dop_cache, band: 2, factor: 0.1},
           ]
    """
    def __init__(self, mode=None):
        self.ops = []
        self.cacheable = True
        self.mode = mode
        self.max_band = {}
        self.max_src_images = 0

    def add_ops(self, dst_band, src_img, src_band, factor=1.0):
        self.ops.append(band_ops(
            dst_band=dst_band,
            src_img=src_img,
            src_band=src_band,
            factor=factor,
         ))
        # store highest requested band index for each source
        self.max_band[src_img] = max(self.max_band.get(src_img, 0), src_band)
        self.max_src_images = max(src_img+1, self.max_src_images)

    def merge(self, sources, image_opts, size=None, bbox=None, bbox_srs=None, coverage=None):
        if len(sources) < self.max_src_images:
            return BlankImageSource(size=size, image_opts=image_opts, cacheable=True)

        if size is None:
            size = sources[0].size

        # load src bands
        src_img_bands = []
        for i, layer_img in enumerate(sources):
            img = layer_img.as_image()

            if i not in self.max_band:
                # do not split img if not requested by any op
                src_img_bands.append(None)
                continue

            if self.max_band[i] == 3 and img.mode != 'RGBA':
                # convert to RGBA if band idx 3 is requestd (e.g. P or RGB src)
                img = img.convert('RGBA')
            elif img.mode == 'P':
                img = img.convert('RGB')
            src_img_bands.append(img.split())

        tmp_mode = self.mode

        if tmp_mode == 'RGBA':
            result_bands = [None, None, None, None]
        elif tmp_mode == 'RGB':
            result_bands = [None, None, None]
        elif tmp_mode == 'L':
            result_bands = [None]
        else:
            raise ValueError("unsupported destination mode %s", image_opts.mode)

        for op in self.ops:
            chan = src_img_bands[op.src_img][op.src_band]
            if op.factor != 1.0:
                chan = ImageMath.eval("convert(int(float(a) * %f), 'L')" % op.factor, a=chan)
                if result_bands[op.dst_band] is None:
                    result_bands[op.dst_band] = chan
                else:
                    result_bands[op.dst_band] = ImageChops.add(
                        result_bands[op.dst_band],
                        chan,
                    )
            else:
                result_bands[op.dst_band] = chan

        for i, b in enumerate(result_bands):
            if b is None:
                # band not set
                b = Image.new("L", size, 255 if i == 3 else 0)
                result_bands[i] = b

        result = Image.merge(tmp_mode, result_bands)
        return ImageSource(result, size=size, image_opts=image_opts)


def merge_images(layers, image_opts, size=None, bbox=None, bbox_srs=None, merger=None):
    """
    Merge multiple images into one.

    :param images: list of `ImageSource`, bottom image first
    :param format: the format of the output `ImageSource`
    :param size: size of the merged image, if ``None`` the size
                 of the first image is used
    :param bbox: Bounding box
    :param bbox_srs: Bounding box SRS
    :param merger: Image merger
    :rtype: `ImageSource`
    """
    if merger is None:
        merger = LayerMerger()

    # BandMerger does not have coverage support, passing only images
    if isinstance(merger, BandMerger):
        sources = [l[0] if isinstance(l, tuple) else l for l in layers]
        return merger.merge(sources, image_opts=image_opts, size=size, bbox=bbox, bbox_srs=bbox_srs)

    for layer in layers:
        if isinstance(layer, tuple):
            merger.add(layer[0], layer[1])
        else:
            merger.add(layer)

    return merger.merge(image_opts=image_opts, size=size, bbox=bbox, bbox_srs=bbox_srs)


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
