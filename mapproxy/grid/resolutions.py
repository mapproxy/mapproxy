import math

from mapproxy.util.bbox import bbox_size


def deg_to_m(deg):
    return deg * (6378137 * 2 * math.pi) / 360


OGC_PIXEL_SIZE = 0.00028  # m/px


def ogc_scale_to_res(scale):
    return scale * OGC_PIXEL_SIZE


def res_to_ogc_scale(res):
    return res / OGC_PIXEL_SIZE


def get_resolution(bbox, size):
    """
    Calculate the highest resolution needed to draw the bbox
    into an image with given size.

    >>> get_resolution((-180,-90,180,90), (256, 256))
    0.703125

    :returns: the resolution
    :rtype: float
    """
    w = abs(bbox[0] - bbox[2])
    h = abs(bbox[1] - bbox[3])
    return min(w/size[0], h/size[1])


def aligned_resolutions(min_res=None, max_res=None, res_factor=2.0, num_levels=None,
                        bbox=None, tile_size=(256, 256), align_with=None):

    alinged_res = align_with.resolutions
    res = list(alinged_res)

    if not min_res:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        min_res = max(width/tile_size[0], height/tile_size[1])

    res = [r for r in res if r <= min_res]

    if max_res:
        res = [r for r in res if r >= max_res]

    if num_levels:
        res = res[:num_levels]

    factor_calculated = res[0]/res[1]
    if res_factor == 'sqrt2' and round(factor_calculated, 8) != round(math.sqrt(2), 8):
        if round(factor_calculated, 8) == 2.0:
            new_res = []
            for r in res:
                new_res.append(r)
                new_res.append(r/math.sqrt(2))
            res = new_res
    elif res_factor == 2.0 and round(factor_calculated, 8) != round(2.0, 8):
        if round(factor_calculated, 8) == round(math.sqrt(2), 8):
            res = res[::2]
    return res


def resolutions(min_res=None, max_res=None, res_factor=2.0, num_levels=None,
                bbox=None, tile_size=(256, 256)):
    if res_factor == 'sqrt2':
        res_factor = math.sqrt(2)

    res = []
    if not min_res:
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        min_res = max(width/tile_size[0], height/tile_size[1])

    if max_res:
        if num_levels:
            res_step = (math.log10(min_res) - math.log10(max_res)) / (num_levels-1)
            res = [10**(math.log10(min_res) - res_step*i) for i in range(num_levels)]
        else:
            res = [min_res]
            while True:
                next_res = res[-1]/res_factor
                if max_res >= next_res:
                    break
                res.append(next_res)
    else:
        if not num_levels:
            num_levels = 20 if res_factor != math.sqrt(2) else 40
        res = [min_res]
        while len(res) < num_levels:
            res.append(res[-1]/res_factor)

    return res


def pyramid_res_level(initial_res, factor=2.0, levels=20):
    """
    Return resolutions of an image pyramid.

    :param initial_res: the resolution of the top level (0)
    :param factor: the factor between each level, for tms access 2
    :param levels: number of resolutions to generate

    >>> list(pyramid_res_level(10000, levels=5))
    [10000.0, 5000.0, 2500.0, 1250.0, 625.0]
    >>> [round(x, 4) for x in
    ...     pyramid_res_level(10000, factor=1/0.75, levels=5)]
    [10000.0, 7500.0, 5625.0, 4218.75, 3164.0625]
    """
    return [initial_res/factor**n for n in range(levels)]


def resolution_range(min_res=None, max_res=None, max_scale=None, min_scale=None):
    if min_scale == max_scale == min_res == max_res is None:
        return None
    if min_res or max_res:
        if not max_scale and not min_scale:
            return ResolutionRange(min_res, max_res)
    elif max_scale or min_scale:
        if not min_res and not max_res:
            min_res = ogc_scale_to_res(max_scale)
            max_res = ogc_scale_to_res(min_scale)
            return ResolutionRange(min_res, max_res)

    raise ValueError('requires either min_res/max_res or max_scale/min_scale')


class ResolutionRange(object):
    def __init__(self, min_res, max_res):
        self.min_res = min_res
        self.max_res = max_res

        if min_res and max_res:
            assert min_res > max_res

    def scale_denominator(self):
        min_scale = res_to_ogc_scale(self.max_res) if self.max_res else None
        max_scale = res_to_ogc_scale(self.min_res) if self.min_res else None
        return min_scale, max_scale

    def scale_hint(self):
        """
        Returns the min and max diagonal resolution.
        """
        min_res = self.min_res
        max_res = self.max_res
        if min_res:
            min_res = math.sqrt(2*min_res**2)
        if max_res:
            max_res = math.sqrt(2*max_res**2)
        return min_res, max_res

    def contains(self, bbox, size, srs):
        width, height = bbox_size(bbox)
        if srs.is_latlong:
            width = deg_to_m(width)
            height = deg_to_m(height)

        x_res = width/size[0]
        y_res = height/size[1]

        if self.min_res:
            min_res = self.min_res + 1e-6
            if min_res <= x_res or min_res <= y_res:
                return False
        if self.max_res:
            max_res = self.max_res
            if max_res > x_res or max_res > y_res:
                return False

        return True

    def __eq__(self, other):
        if not isinstance(other, ResolutionRange):
            return NotImplemented

        return (self.min_res == other.min_res
                and self.max_res == other.max_res)

    def __ne__(self, other):
        if not isinstance(other, ResolutionRange):
            return NotImplemented
        return not self == other

    def __repr__(self):
        return '<ResolutionRange(min_res=%.3f, max_res=%.3f)>' % (
            self.min_res or 9e99, self.max_res or 0)


def max_with_none(a, b):
    if a is None or b is None:
        return None
    else:
        return max(a, b)


def min_with_none(a, b):
    if a is None or b is None:
        return None
    else:
        return min(a, b)


def merge_resolution_range(a, b):
    if a and b:
        return resolution_range(min_res=max_with_none(a.min_res, b.min_res),
                                max_res=min_with_none(a.max_res, b.max_res))
    return None
