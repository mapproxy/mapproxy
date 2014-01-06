"""
Retrieve maps/information from WMS servers.
"""
from mapproxy.source.wms import WMSSource

import logging
log = logging.getLogger('mapproxy.source.arcgis')


class ArcGISSource(WMSSource):
    def __init__(self, client, image_opts = None, coverage = None,
                 supported_srs = None, supported_formats = None):
        WMSSource.__init__(self, client, image_opts = image_opts, coverage = coverage,
                           supported_srs = supported_srs, supported_formats = supported_formats)

        # It appears that there are some limitations related to the size and/or
        # how the image aspect ratio relates to the bbox.
        self.supports_meta_tiles = False
