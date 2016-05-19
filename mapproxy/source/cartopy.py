# This module is released under the BSD 3-clause license by Philip Elson (@pelson) 2016.

from __future__ import with_statement, absolute_import

import io
import sys
import time

import cartopy.crs as ccrs
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt

from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, MapLayer
from mapproxy.source import SourceError
from mapproxy.client.log import log_request
from mapproxy.util.py import reraise_exception


class CartopySource(MapLayer):
    supports_meta_tiles = False

    def __init__(self, axes_function, layers=None, image_opts=None, coverage=None,
                 res_range=None, lock=None, reuse_map_objects=False, scale_factor=None):
        MapLayer.__init__(self, image_opts=image_opts)
        self.axes_function = axes_function
        self.coverage = coverage
        self.res_range = res_range
        self.layers = set(layers) if layers else None
        self.scale_factor = scale_factor
        self.lock = lock
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        self._axes_cache = {}

    def get_map(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()

        try:
            resp = self.render(query)
        except RuntimeError as ex:
            reraise_exception(SourceError(ex.args[0]), sys.exc_info())
        return resp

    def render(self, query):
        if self.lock:
            with self.lock():
                return self._render(query)
        else:
            return self._render(query)

    def _render(self, query):
        start_time = time.time()
        proj_code = '+init=%s' % str(query.srs.srs_code.lower())
        envelope = query.bbox
        if proj_code in ['+init=crs:84', '+init=epsg:4326']:
            crs = ccrs.PlateCarree()
        elif proj_code in ['+init=epsg:3857', '+init=epsg:3785', '+init=epsg:900913']:
            # TODO: I'm not sure this it correct.
            crs = ccrs.Mercator.GOOGLE
        else:
            raise ValueError('Unsupported projection {}'.format(proj_code))

        def _prepare_axes(ax):
            ax.outline_patch.set_visible(False)
            ax.background_patch.set_visible(False)
            ax.set_aspect('auto')
            ax.set_xlim(envelope[0], envelope[2])
            ax.set_ylim(envelope[1], envelope[3])
            ax._mapproxy_context = {'self': self, 'query': query}

            fig = ax.figure
            fig.set_size_inches((query.size[0]/100, query.size[1]/100))
            fig.set_dpi(100)

        if proj_code not in self._axes_cache:
            fig = plt.figure()
            ax = fig.add_axes([0, 0, 1, 1], projection=crs)
            _prepare_axes(ax)
            self.axes_function(ax)
            self._axes_cache[proj_code] = ax

        ax = self._axes_cache[proj_code]
        _prepare_axes(ax)

        data = io.BytesIO()
        ax.figure.savefig(data, format=str(query.format), dpi=100, transparent=True)
        data.seek(0)
        log_request('%s:%s:%s:%s' % (proj_code, query.bbox, query.srs.srs_code, query.size),
                    status='200', method='API', duration=time.time()-start_time)
        return ImageSource(data, size=query.size,
                           image_opts=ImageOptions(transparent=self.transparent,
                                                   format=query.format))
