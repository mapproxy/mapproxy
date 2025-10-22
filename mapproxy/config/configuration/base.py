from __future__ import division


class ConfigurationBase(object):
    """
    Base class for all configurations.
    """
    defaults: dict = {}

    def __init__(self, conf, context):
        """
        :param conf: the configuration part for this configurator
        :param context: the complete proxy configuration
        :type context: config.configuration.proxy.ProxyConfiguration
        """
        self.conf = conf
        self.context = context
        for k, v in self.defaults.items():
            if k not in self.conf:
                self.conf[k] = v


class ConfigurationError(Exception):
    pass


def parse_color(color):
    """
    >>> parse_color((100, 12, 55))
    (100, 12, 55)
    >>> parse_color('0xff0530')
    (255, 5, 48)
    >>> parse_color('#FF0530')
    (255, 5, 48)
    >>> parse_color('#FF053080')
    (255, 5, 48, 128)
    """
    if isinstance(color, (list, tuple)) and 3 <= len(color) <= 4:
        return tuple(color)
    if not isinstance(color, str):
        raise ValueError('color needs to be a tuple/list or 0xrrggbb/#rrggbb(aa) string, got %r' % color)

    if color.startswith('0x'):
        color = color[2:]
    if color.startswith('#'):
        color = color[1:]

    r, g, b = map(lambda x: int(x, 16), [color[:2], color[2:4], color[4:6]])

    if len(color) == 8:
        a = int(color[6:8], 16)
        return r, g, b, a

    return r, g, b


def dotted_dict_get(key, d):
    """
    >>> dotted_dict_get('foo', {'foo': {'bar': 1}})
    {'bar': 1}
    >>> dotted_dict_get('foo.bar', {'foo': {'bar': 1}})
    1
    >>> dotted_dict_get('bar', {'foo': {'bar': 1}})
    """
    parts = key.split('.')
    try:
        while parts and d:
            d = d[parts.pop(0)]
    except KeyError:
        return None
    if parts:  # not completely resolved
        return None
    return d
