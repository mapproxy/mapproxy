from __future__ import division

import warnings

from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.config.configuration.base import ConfigurationError

default_image_options: dict = {
}


class ImageOptionsConfiguration(ConfigurationBase):
    def __init__(self, conf, context):
        ConfigurationBase.__init__(self, conf, context)
        self._init_formats()

    def _init_formats(self):
        self.formats = {}

        formats_config = default_image_options.copy()
        for format, conf in self.conf.get('formats', {}).items():
            if format in formats_config:
                tmp = formats_config[format].copy()
                tmp.update(conf)
                conf = tmp
            if 'resampling_method' in conf:
                conf['resampling'] = conf.pop('resampling_method')
            if 'encoding_options' in conf:
                self._check_encoding_options(conf['encoding_options'])
            if 'merge_method' in conf:
                warnings.warn('merge_method now defaults to composite. option no longer required',
                              DeprecationWarning)
            formats_config[format] = conf
        for format, conf in formats_config.items():
            if 'format' not in conf and format.startswith('image/'):
                conf['format'] = format
            self.formats[format] = conf

    def _check_encoding_options(self, options):
        if not options:
            return
        options = options.copy()
        jpeg_quality = options.pop('jpeg_quality', None)
        if jpeg_quality and not isinstance(jpeg_quality, int):
            raise ConfigurationError('jpeg_quality is not an integer')

        tiff_compression = options.pop('tiff_compression', None)
        if tiff_compression and tiff_compression not in ('raw', 'tiff_lzw', 'jpeg'):
            raise ConfigurationError('unknown tiff_compression')

        quantizer = options.pop('quantizer', None)
        if quantizer and quantizer not in ('fastoctree', 'mediancut'):
            raise ConfigurationError('unknown quantizer')

        if options:
            raise ConfigurationError('unknown encoding_options: %r' % options)

    def image_opts(self, image_conf, format):
        from mapproxy.image.opts import ImageOptions
        if not image_conf:
            image_conf = {}

        conf = {}
        if format in self.formats:
            conf = self.formats[format].copy()

        resampling = image_conf.get('resampling_method') or conf.get('resampling')
        if resampling is None:
            resampling = self.context.globals.get_value('image.resampling_method', {})
        transparent = image_conf.get('transparent')
        opacity = image_conf.get('opacity')
        img_format = image_conf.get('format')
        colors = image_conf.get('colors')
        mode = image_conf.get('mode')
        encoding_options = image_conf.get('encoding_options')
        if 'merge_method' in image_conf:
            warnings.warn('merge_method now defaults to composite. option no longer required',
                          DeprecationWarning)

        self._check_encoding_options(encoding_options)

        # only overwrite default if it is not None
        for k, v in dict(
                transparent=transparent, opacity=opacity, resampling=resampling,
                format=img_format, colors=colors, mode=mode, encoding_options=encoding_options,
        ).items():
            if v is not None:
                conf[k] = v

        if 'format' not in conf and format and format.startswith('image/'):
            conf['format'] = format

        # caches shall be able to store png and jpeg tiles with mixed format
        if format == 'mixed':
            conf['format'] = format
            conf['transparent'] = True

        # force 256 colors for image.paletted for backwards compat
        paletted = self.context.globals.get_value('image.paletted', self.conf)
        if conf.get('colors') is None and 'png' in conf.get('format', '') and paletted:
            conf['colors'] = 256

        opts = ImageOptions(**conf)
        return opts
