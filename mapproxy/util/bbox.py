class TransformationError(Exception):
    pass


def calculate_bbox(points):
    """
    Calculates the bbox of a list of points.

    >>> calculate_bbox([(-5, 20), (3, 8), (99, 0)])
    (-5, 0, 99, 20)

    @param points: list of points [(x0, y0), (x1, y2), ...]
    @returns: bbox of the input points.
    """
    points = list(points)
    # points can be INF for invalid transformations, filter out
    try:
        minx = min(p[0] for p in points if p[0] != float('inf'))
        miny = min(p[1] for p in points if p[1] != float('inf'))
        maxx = max(p[0] for p in points if p[0] != float('inf'))
        maxy = max(p[1] for p in points if p[1] != float('inf'))
        return (minx, miny, maxx, maxy)
    except ValueError:  # min/max are called with empty list when everything is inf
        raise TransformationError()


def merge_bbox(bbox1, bbox2):
    """
    Merge two bboxes.

    >>> merge_bbox((-10, 20, 0, 30), (30, -20, 90, 10))
    (-10, -20, 90, 30)

    """
    minx = min(bbox1[0], bbox2[0])
    miny = min(bbox1[1], bbox2[1])
    maxx = max(bbox1[2], bbox2[2])
    maxy = max(bbox1[3], bbox2[3])
    return (minx, miny, maxx, maxy)


def bbox_equals(src_bbox, dst_bbox, x_delta=None, y_delta=None):
    """
    Compares two bbox and checks if they are equal, or nearly equal.

    :param x_delta: how precise the comparison should be.
                    should be reasonable small, like a tenth of a pixel.
                    defaults to 1/1.000.000th of the width.
    :type x_delta: bbox units

    >>> src_bbox = (939258.20356824622, 6887893.4928338043,
    ...             1095801.2374962866, 7044436.5267618448)
    >>> dst_bbox = (939258.20260000182, 6887893.4908000007,
    ...             1095801.2365000017, 7044436.5247000009)
    >>> bbox_equals(src_bbox, dst_bbox, 61.1, 61.1)
    True
    >>> bbox_equals(src_bbox, dst_bbox, 0.0001)
    False
    """
    if x_delta is None:
        x_delta = abs(src_bbox[0] - src_bbox[2]) / 1000000.0
    if y_delta is None:
        y_delta = x_delta
    return (abs(src_bbox[0] - dst_bbox[0]) < x_delta and
            abs(src_bbox[1] - dst_bbox[1]) < x_delta and
            abs(src_bbox[2] - dst_bbox[2]) < y_delta and
            abs(src_bbox[3] - dst_bbox[3]) < y_delta)


def bbox_tuple(bbox):
    """
    >>> bbox_tuple('20,-30,40,-10')
    (20.0, -30.0, 40.0, -10.0)
    >>> bbox_tuple([20,-30,40,-10])
    (20.0, -30.0, 40.0, -10.0)

    """
    if isinstance(bbox, str):
        bbox = bbox.split(',')
    bbox = tuple(map(float, bbox))
    return bbox


def bbox_width(bbox):
    return bbox[2] - bbox[0]


def bbox_height(bbox):
    return bbox[3] - bbox[1]


def bbox_size(bbox):
    return bbox_width(bbox), bbox_height(bbox)


def bbox_intersects(one, two):
    a_x0, a_y0, a_x1, a_y1 = one
    b_x0, b_y0, b_x1, b_y1 = two

    if (
            a_x0 < b_x1 and
            a_x1 > b_x0 and
            a_y0 < b_y1 and
            a_y1 > b_y0
    ):
        return True

    return False


def bbox_contains(one, two):
    """
    Returns ``True`` if `one` contains `two`.

    >>> bbox_contains([0, 0, 10, 10], [2, 2, 4, 4])
    True
    >>> bbox_contains([0, 0, 10, 10], [0, 0, 11, 10])
    False

    Allow tiny rounding errors:

    >>> bbox_contains([0, 0, 10, 10], [0.000001, 0.0000001, 10.000001, 10.000001])
    False
    >>> bbox_contains([0, 0, 10, 10], [0.0000000000001, 0.0000000000001, 10.0000000000001, 10.0000000000001])
    True
    """
    a_x0, a_y0, a_x1, a_y1 = one
    b_x0, b_y0, b_x1, b_y1 = two

    x_delta = abs(a_x1 - a_x0) / 10e12
    y_delta = abs(a_y1 - a_y0) / 10e12

    if (
            a_x0 <= b_x0 + x_delta and
            a_x1 >= b_x1 - x_delta and
            a_y0 <= b_y0 + y_delta and
            a_y1 >= b_y1 - y_delta
    ):
        return True

    return False
