# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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

from mapproxy.platform.image import Image
from mapproxy.image import ImageSource, image_filter
from mapproxy.srs import make_lin_transf, bbox_equals

class ImageTransformer(object):
    """
    Transform images between different bbox and spatial reference systems.
    
    :note: The transformation doesn't make a real transformation for each pixel,
           but a mesh transformation (see `PIL Image.transform`_).
           It will divide the target image into rectangles (a mesh). The
           source coordinates for each rectangle vertex will be calculated.
           The quadrilateral will then be transformed with the source coordinates
           into the destination quad (affine).
           
           This method will perform good transformation results if the number of
           quads is high enough (even transformations with strong distortions).
           Tests on images up to 1500x1500 have shown that meshes beyond 8x8
           will not improve the results.
           
           .. _PIL Image.transform:
              http://www.pythonware.com/library/pil/handbook/image.htm#Image.transform
           
           ::
              
                    src quad                   dst quad
                    .----.   <- coord-           .----.
                   /    /       transformation   |    |
                  /    /                         |    |
                 .----.   img-transformation ->  .----.----
                           |                     |    |
            ---------------.
            large src image                   large dst image
    """
    def __init__(self, src_srs, dst_srs, mesh_div=8):
        """
        :param src_srs: the srs of the source image
        :param dst_srs: the srs of the target image
        :param resampling: the resampling method used for transformation
        :type resampling: nearest|bilinear|bicubic
        :param mesh_div: the number of quads in each direction to use
                         for transformation (totals to ``mesh_div**2`` quads)
        
        """
        self.src_srs = src_srs
        self.dst_srs = dst_srs
        self.mesh_div = mesh_div
        self.dst_bbox = self.dst_size = None
    
    def transform(self, src_img, src_bbox, dst_size, dst_bbox, image_opts):
        """
        Transforms the `src_img` between the source and destination SRS
        of this ``ImageTransformer`` instance.
        
        When the ``src_srs`` and ``dst_srs`` are equal the image will be cropped
        and not transformed. If the `src_bbox` and `dst_bbox` are equal,
        the `src_img` itself will be returned.
        
        :param src_img: the source image for the transformation
        :param src_bbox: the bbox of the src_img
        :param dst_size: the size of the result image (in pizel)
        :type dst_size: ``(int(width), int(height))``
        :param dst_bbox: the bbox of the result image
        :return: the transformed image
        :rtype: `ImageSource`
        """
        if self._no_transformation_needed(src_img.size, src_bbox, dst_size, dst_bbox):
            return src_img
        elif self.src_srs == self.dst_srs:
            return self._transform_simple(src_img, src_bbox, dst_size, dst_bbox,
                image_opts)
        else:
            return self._transform(src_img, src_bbox, dst_size, dst_bbox, image_opts)
    
    def _transform_simple(self, src_img, src_bbox, dst_size, dst_bbox, image_opts):
        """
        Do a simple crop/extent transformation.
        """
        src_quad = (0, 0, src_img.size[0], src_img.size[1])
        to_src_px = make_lin_transf(src_bbox, src_quad)
        minx, miny = to_src_px((dst_bbox[0], dst_bbox[3]))
        maxx, maxy = to_src_px((dst_bbox[2], dst_bbox[1]))
        
        src_res = ((src_bbox[0]-src_bbox[2])/src_img.size[0],
                   (src_bbox[1]-src_bbox[3])/src_img.size[1])
        dst_res = ((dst_bbox[0]-dst_bbox[2])/dst_size[0],
                   (dst_bbox[1]-dst_bbox[3])/dst_size[1])
        
        tenth_px_res = (abs(dst_res[0]/(dst_size[0]*10)),
                        abs(dst_res[1]/(dst_size[1]*10)))
        if (abs(src_res[0]-dst_res[0]) < tenth_px_res[0] and
            abs(src_res[1]-dst_res[1]) < tenth_px_res[1]):
            # rounding might result in subpixel inaccuracy
            # this exact resolutioni match should only happen in clients with
            # fixed resolutions like OpenLayers
            minx = int(round(minx))
            miny = int(round(miny))
            result = src_img.as_image().crop((minx, miny,
                                              minx+dst_size[0], miny+dst_size[1]))
        else:
            result = src_img.as_image().transform(dst_size, Image.EXTENT,
                                                  (minx, miny, maxx, maxy),
                                                  image_filter[image_opts.resampling])
        return ImageSource(result, size=dst_size, image_opts=image_opts)
    
    def _transform(self, src_img, src_bbox, dst_size, dst_bbox, image_opts):
        """
        Do a 'real' transformation with a transformed mesh (see above).
        """
        src_bbox = self.src_srs.align_bbox(src_bbox)
        dst_bbox = self.dst_srs.align_bbox(dst_bbox)
        src_size = src_img.size
        src_quad = (0, 0, src_size[0], src_size[1])
        dst_quad = (0, 0, dst_size[0], dst_size[1])
        to_src_px = make_lin_transf(src_bbox, src_quad)
        to_dst_w = make_lin_transf(dst_quad, dst_bbox)
        meshes = []
        def dst_quad_to_src(quad):
            src_quad = []
            for dst_px in [(quad[0], quad[1]), (quad[0], quad[3]),
                           (quad[2], quad[3]), (quad[2], quad[1])]:
                dst_w = to_dst_w((dst_px[0]+0.5, dst_px[1]+0.5))
                src_w = self.dst_srs.transform_to(self.src_srs, dst_w)
                src_px = to_src_px(src_w)
                src_quad.extend(src_px)
            return quad, src_quad
        
        mesh_div = self.mesh_div
        while mesh_div > 1 and (dst_size[0] / mesh_div < 10 or dst_size[1] / mesh_div < 10):
            mesh_div -= 1
        for quad in griddify(dst_quad, mesh_div):
            meshes.append(dst_quad_to_src(quad))

        result = src_img.as_image().transform(dst_size, Image.MESH, meshes,
                                              image_filter[image_opts.resampling])
        return ImageSource(result, size=dst_size, image_opts=image_opts)
        
    def _no_transformation_needed(self, src_size, src_bbox, dst_size, dst_bbox):
        """
        >>> src_bbox = (-2504688.5428486541, 1252344.271424327,
        ...             -1252344.271424327, 2504688.5428486541)
        >>> dst_bbox = (-2504688.5431999983, 1252344.2704,
        ...             -1252344.2719999983, 2504688.5416000001)
        >>> from mapproxy.srs import SRS
        >>> t = ImageTransformer(SRS(900913), SRS(900913))
        >>> t._no_transformation_needed((256, 256), src_bbox, (256, 256), dst_bbox)
        True
        """
        xres = (dst_bbox[2]-dst_bbox[0])/dst_size[0]
        yres = (dst_bbox[3]-dst_bbox[1])/dst_size[1]
        return (src_size == dst_size and
                self.src_srs == self.dst_srs and
                bbox_equals(src_bbox, dst_bbox, xres/10, yres/10))
    

def griddify(quad, steps):
    """
    Divides a box (`quad`) into multiple boxes (``steps x steps``).
    
    >>> list(griddify((0, 0, 500, 500), 2))
    [(0, 0, 250, 250), (250, 0, 500, 250), (0, 250, 250, 500), (250, 250, 500, 500)]
    """
    w = quad[2]-quad[0]
    h = quad[3]-quad[1]
    x_step = w / float(steps)
    y_step = h / float(steps)
    
    y = quad[1]
    for _ in range(steps):
        x = quad[0]
        for _ in range(steps):
            yield (int(x), int(y), int(x+x_step), int(y+y_step))
            x += x_step
        y += y_step
