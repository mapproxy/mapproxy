from __future__ import division

from mapproxy.config.configuration.base import ConfigurationError
from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.util.py import memoize

import logging

log = logging.getLogger('mapproxy.config')


class GridConfiguration(ConfigurationBase):
    @memoize
    def tile_grid(self):
        from mapproxy.grid.tile_grid import tile_grid

        if 'base' in self.conf:
            base_grid_name = self.conf['base']
            if base_grid_name not in self.context.grids:
                raise ConfigurationError('unknown base %s for grid %s' % (base_grid_name, self.conf['name']))
            conf = self.context.grids[base_grid_name].conf.copy()
            conf.update(self.conf)
            conf.pop('base')
            self.conf = conf
        else:
            conf = self.conf
        align_with = None
        if 'align_resolutions_with' in self.conf:
            align_with_grid_name = self.conf['align_resolutions_with']
            align_with = self.context.grids[align_with_grid_name].tile_grid()

        tile_size = self.context.globals.get_value('tile_size', conf,
                                                   global_key='grid.tile_size')
        conf['tile_size'] = tuple(tile_size)
        tile_size = tuple(tile_size)

        stretch_factor = self.context.globals.get_value('stretch_factor', conf,
                                                        global_key='image.stretch_factor')
        max_shrink_factor = self.context.globals.get_value('max_shrink_factor', conf,
                                                           global_key='image.max_shrink_factor')

        if conf.get('origin') is None:
            log.warning(
                'grid %s does not have an origin. default origin will change from sw (south/west) to nw (north-west)'
                ' with MapProxy 2.0', conf['name'])

        grid = tile_grid(
            name=conf['name'],
            srs=conf.get('srs'),
            tile_size=tile_size,
            min_res=conf.get('min_res'),
            max_res=conf.get('max_res'),
            res=conf.get('res'),
            res_factor=conf.get('res_factor', 2.0),
            threshold_res=conf.get('threshold_res'),
            bbox=conf.get('bbox'),
            bbox_srs=conf.get('bbox_srs'),
            num_levels=conf.get('num_levels'),
            stretch_factor=stretch_factor,
            max_shrink_factor=max_shrink_factor,
            align_with=align_with,
            origin=conf.get('origin')
        )

        return grid
