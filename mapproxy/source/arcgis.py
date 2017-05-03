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

from mapproxy.source.wms import WMSSource, WMSInfoSource

import logging
log = logging.getLogger('mapproxy.source.arcgis')


class ArcGISSource(WMSSource):
    def __init__(self, client, image_opts=None, coverage=None,
                 res_range=None, supported_srs=None, supported_formats=None):
        WMSSource.__init__(self, client, image_opts=image_opts,
                           coverage=coverage, res_range=res_range,
                           supported_srs=supported_srs,
                           supported_formats=supported_formats)


class ArcGISInfoSource(WMSInfoSource):
    def __init__(self, client):
        self.client = client

    def get_info(self, query):
        doc = self.client.get_info(query)
        return doc