# This file is part of the MapProxy project.
# Copyright (C) 2025 Spatialys
#
# Initial development funded by Centre National d'Etudes Spatiales (CNES): https://cnes.fr
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

from collections import OrderedDict

F_JSON = "json"
F_HTML = "html"
F_PNG = "png"
F_JPEG = "jpeg"

#: Formats allowed for ?f= requests (order matters for complex MIME types)
FORMAT_TYPES = OrderedDict(
    (
        (F_HTML, "text/html"),
        (F_JSON, "application/json"),
        (F_PNG, "image/png"),
        (F_JPEG, "image/jpeg"),
    )
)

MEDIA_TYPE_OPENAPI_3_0 = "application/vnd.oai.openapi+json;version=3.0"
