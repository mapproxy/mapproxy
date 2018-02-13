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

from mapproxy.compat.image import Image, transform_uses_center
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

           The number of quads is calculated dynamically to keep the deviation in
           the image transformation below one pixel.

           .. _PIL Image.transform:
              http://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.transform

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
    def __init__(self, src_srs, dst_srs, max_px_err=1):
        """
        :param src_srs: the srs of the source image
        :param dst_srs: the srs of the target image
        :param resampling: the resampling method used for transformation
        :type resampling: nearest|bilinear|bicubic
        """
        self.src_srs = src_srs
        self.dst_srs = dst_srs
        self.dst_bbox = self.dst_size = None
        self.max_px_err = max_px_err

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

        if self.src_srs == self.dst_srs:
            result = self._transform_simple(src_img, src_bbox, dst_size, dst_bbox,
                image_opts)
        else:
            result = self._transform(src_img, src_bbox, dst_size, dst_bbox, image_opts)

        result.cacheable = src_img.cacheable
        return result

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
            img = img_for_resampling(src_img.as_image(), image_opts.resampling)
            result = img.transform(dst_size, Image.EXTENT,
                                                  (minx, miny, maxx, maxy),
                                                  image_filter[image_opts.resampling])
        return ImageSource(result, size=dst_size, image_opts=image_opts)

    def _transform(self, src_img, src_bbox, dst_size, dst_bbox, image_opts):
        """
        Do a 'real' transformation with a transformed mesh (see above).
        """

        # more recent versions of Pillow use center coordinates for
        # transformations, we manually need to add half a pixel otherwise
        if transform_uses_center():
            use_center_px = False
        else:
            use_center_px = True

        meshes = transform_meshes(
            src_size=src_img.size,
            src_bbox=src_bbox,
            src_srs=self.src_srs,
            dst_size=dst_size,
            dst_bbox=dst_bbox,
            dst_srs=self.dst_srs,
            max_px_err=self.max_px_err,
            use_center_px=use_center_px,
        )

        img = img_for_resampling(src_img.as_image(), image_opts.resampling)
        result = img.transform(dst_size, Image.MESH, meshes,
                                              image_filter[image_opts.resampling])

        if False:
            # draw mesh for debuging
            from PIL import ImageDraw
            draw = ImageDraw.Draw(result)
            for g, _ in meshes:
                draw.rectangle(g, fill=None, outline=(255, 0, 0))

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


def transform_meshes(
        src_size, src_bbox, src_srs,
        dst_size, dst_bbox, dst_srs,
        max_px_err=1,
        use_center_px=False,
    ):
    """
    transform_meshes creates a list of QUAD transformation parameters for PIL's
    MESH image transformation.

    Each QUAD is a rectangle in the destination image, like ``(0, 0, 100, 100)`` and
    a list of four pixel coordinates in the source image that match the destination rectangle.
    The four points form a quadliteral (i.e. not a rectangle).
    PIL's image transform uses affine transformation to fill each rectangle in the destination
    image with data from the source quadliteral.

    The number of QUADs is calculated dynamically to keep the deviation in the image
    transformation below one pixel. Image transformations for large map scales can be transformed with
    1-4 QUADs most of the time. For low scales, transform_meshes can generate a few hundred QUADs.

    It generates a maximum of one QUAD per 50 pixel.
    """
    src_bbox = src_srs.align_bbox(src_bbox)
    dst_bbox = dst_srs.align_bbox(dst_bbox)
    src_rect = (0, 0, src_size[0], src_size[1])
    dst_rect = (0, 0, dst_size[0], dst_size[1])
    to_src_px = make_lin_transf(src_bbox, src_rect)
    to_src_w = make_lin_transf(src_rect, src_bbox)
    to_dst_w = make_lin_transf(dst_rect, dst_bbox)
    meshes = []

    if use_center_px:
        px_offset = 0.5
    else:
        px_offset = 0.0

    def dst_quad_to_src(quad):
        src_quad = []
        for dst_px in [(quad[0], quad[1]), (quad[0], quad[3]),
                        (quad[2], quad[3]), (quad[2], quad[1])]:
            dst_w = to_dst_w(
                (dst_px[0] + px_offset, dst_px[1] + px_offset))
            src_w = dst_srs.transform_to(src_srs, dst_w)
            src_px = to_src_px(src_w)
            src_quad.extend(src_px)

        return quad, src_quad

    res = (dst_bbox[2] - dst_bbox[0]) / dst_size[0]
    max_err = max_px_err * res

    def is_good(quad, src_quad):
        w = quad[2] - quad[0]
        h = quad[3] - quad[1]

        if w < 50 or h < 50:
            return True

        xc = quad[0] + w / 2.0 - 0.5
        yc = quad[1] + h / 2.0 - 0.5

        # coordinate for the center of the quad
        dst_w = to_dst_w((xc, yc))

        # actual coordinate for the center of the quad
        src_px = center_quad_transform(quad, src_quad)
        real_dst_w = src_srs.transform_to(dst_srs, to_src_w(src_px))

        err = max(abs(dst_w[0] - real_dst_w[0]), abs(dst_w[1] - real_dst_w[1]))
        return err < max_err


    # recursively add meshes. divide each quad into four sub quad till
    # accuracy is good enough.
    def add_meshes(quads):
        for quad in quads:
            quad, src_quad = dst_quad_to_src(quad)
            if is_good(quad, src_quad):
                meshes.append((quad, src_quad))
            else:
                add_meshes(divide_quad(quad))

    add_meshes([(0, 0, dst_size[0], dst_size[1])])
    return meshes


def center_quad_transform(quad, src_quad):
    """
    center_quad_transfrom transforms the center pixel coordinates
    from ``quad`` to ``src_quad`` by using affine transformation
    as used by PIL.Image.transform.
    """
    w = quad[2] - quad[0]
    h = quad[3] - quad[1]

    nw = src_quad[0:2]
    sw = src_quad[2:4]
    se = src_quad[4:6]
    ne = src_quad[6:8]
    x0, y0 = nw
    As = 1.0 / w
    At = 1.0 / h

    a0 = x0
    a1 = (ne[0] - x0) * As
    a2 = (sw[0] - x0) * At
    a3 = (se[0] - sw[0] - ne[0] + x0) * As * At
    a4 = y0
    a5 = (ne[1] - y0) * As
    a6 = (sw[1] - y0) * At
    a7 = (se[1] - sw[1] - ne[1] + y0) * As * At

    x = w / 2.0 - 0.5
    y = h / 2.0 - 0.5

    return (
        a0 + a1*x + a2*y + a3*x*y,
        a4 + a5*x + a6*y + a7*x*y
    )


def img_for_resampling(img, resampling):
    """
    Convert P images to RGB(A) for non-NEAREST resamplings.
    """
    resampling = image_filter[resampling]
    if img.mode == 'P' and resampling != Image.NEAREST:
        img.load() # load to get actual palette mode
        if img.palette is not None:
            # palette can still be None for cropped images
            img = img.convert(img.palette.mode)
        else:
            img = img.convert('RGBA')
    return img


def divide_quad(quad):
    """
    divide_quad in up to four sub quads. Only divide horizontal if quad is twice as wide then high,
    and vertical vice versa.
    PIL.Image.transform expects that the lower-right corner
    of a quad overlaps by one pixel.

    >>> divide_quad((0, 0, 500, 500))
    [(0, 0, 250, 250), (250, 0, 500, 250), (0, 250, 250, 500), (250, 250, 500, 500)]
    >>> divide_quad((0, 0, 2000, 500))
    [(0, 0, 1000, 500), (1000, 0, 2000, 500)]
    >>> divide_quad((100, 200, 200, 500))
    [(100, 200, 200, 350), (100, 350, 200, 500)]

    """
    w = quad[2] - quad[0]
    h = quad[3] - quad[1]
    xc = int(quad[0] + w/2)
    yc = int(quad[1] + h/2)

    if w > 2*h:
        return [
            (quad[0], quad[1], xc, quad[3]),
            (xc, quad[1], quad[2], quad[3]),
        ]
    if h > 2*w:
        return [
            (quad[0], quad[1], quad[2], yc),
            (quad[0], yc, quad[2], quad[3]),
        ]

    return [
        (quad[0], quad[1], xc, yc),
        (xc, quad[1], quad[2], yc),
        (quad[0], yc, xc, quad[3]),
        (xc, yc, quad[2], quad[3]),
    ]
