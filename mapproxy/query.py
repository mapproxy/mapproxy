from __future__ import division

from mapproxy.srs import make_lin_transf


class MapQuery(object):
    """
    Internal query for a map with a specific extent, size, srs, etc.
    """

    def __init__(self, bbox, size, srs, format='image/png', transparent=False,
                 tiled_only=False, dimensions=None):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.format = format
        self.transparent = transparent
        self.tiled_only = tiled_only
        self.dimensions = dimensions or {}

    def dimensions_for_params(self, params):
        """
        Return subset of the dimensions.

        >>> mq = MapQuery(None, None, None, dimensions={'Foo': 1, 'bar': 2})
        >>> mq.dimensions_for_params(set(['FOO', 'baz']))
        {'Foo': 1}
        """
        params = [p.lower() for p in params]
        return dict((k, v) for k, v in self.dimensions.items() if k.lower() in params)

    def __repr__(self):
        info = self.__dict__
        serialized_dimensions = ", ".join(["'%s': '%s'" % (key, value) for (key, value) in self.dimensions.items()])
        info["serialized_dimensions"] = serialized_dimensions
        return ("MapQuery(bbox=%(bbox)s, size=%(size)s, srs=%(srs)r, format=%(format)s,"
                " dimensions={%(serialized_dimensions)s)}") % info


class InfoQuery(object):
    def __init__(self, bbox, size, srs, pos, info_format, format=None,
                 feature_count=None):
        self.bbox = bbox
        self.size = size
        self.srs = srs
        self.pos = pos
        self.info_format = info_format
        self.format = format
        self.feature_count = feature_count

    @property
    def coord(self):
        return make_lin_transf((0, 0, self.size[0], self.size[1]), self.bbox)(self.pos)


class LegendQuery(object):
    def __init__(self, format, scale):
        self.format = format
        self.scale = scale
