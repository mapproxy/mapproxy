# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mapproxy.core.image import ImageSource, ImageTransformer
from mapproxy.core.client import retrieve_url, HTTPClientError
from mapproxy.core.srs import SRS, make_lin_transf


def wms_client_request(request_template, map_request):
    if request_template is None:
        return map_request.copy()
    req = request_template.copy_with_request_params(map_request)
    req.url = request_template.url
    req.params.bbox = map_request.params.bbox
    if map_request.params.srs:
        req.params.srs = map_request.params.srs
    return req
