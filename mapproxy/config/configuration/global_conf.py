from __future__ import division

import os

from mapproxy.config import load_default_config, finish_base_config
from mapproxy.config.configuration.base import ConfigurationBase
from mapproxy.config.configuration.base import dotted_dict_get
from mapproxy.config.configuration.image_options import ImageOptionsConfiguration


def preferred_srs(conf):
    from mapproxy.srs import SRS, PreferredSrcSRS

    preferred_conf = conf.get('preferred_src_proj', {})

    if not preferred_conf:
        return

    preferred = PreferredSrcSRS()

    for target, preferred_srcs in preferred_conf.items():
        preferred.add(SRS(target), [SRS(s) for s in preferred_srcs])

    return preferred


class GlobalConfiguration(ConfigurationBase):
    def __init__(self, conf_base_dir, conf, context):
        ConfigurationBase.__init__(self, conf, context)
        self.base_config = load_default_config()
        self._copy_conf_values(self.conf, self.base_config)
        self.base_config.conf_base_dir = conf_base_dir
        finish_base_config(self.base_config)

        self.image_options = ImageOptionsConfiguration(self.conf.get('image', {}), context)
        self.preferred_srs = preferred_srs(self.conf.get('srs', {}))
        self.renderd_address = self.get_value('renderd.address')

    def _copy_conf_values(self, d, target):
        for k, v in d.items():
            if v is None:
                continue
            if (hasattr(v, 'iteritems') or hasattr(v, 'items')) and k in target:
                self._copy_conf_values(v, target[k])
            else:
                target[k] = v

    def get_value(self, key, local={}, global_key=None, default_key=None):
        result = dotted_dict_get(key, local)
        if result is None:
            result = dotted_dict_get(global_key or key, self.conf)

        if result is None:
            result = dotted_dict_get(default_key or global_key or key, self.base_config)

        return result

    def get_path(self, key, local, global_key=None, default_key=None):
        value = self.get_value(key, local, global_key, default_key)
        if value is not None:
            value = self.abspath(value)
        return value

    def abspath(self, path):
        return os.path.join(self.base_config.conf_base_dir, path)
