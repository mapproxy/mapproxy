# This file is part of the MapProxy project.
# Copyright (C) 2012 Omniscale <http://omniscale.de>
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

from mapproxy.image.opts import ImageOptions
from mapproxy.image import BlankImageSource

class HTTPSourceErrorHandler(object):
	def __init__(self):
		self.response_error_codes = {}
	
	def add_handler(self, http_code, color, cacheable=False):
		self.response_error_codes[http_code] = (color, cacheable)

	def handle(self, status_code, query):
		color = cacheable = None
		if status_code in self.response_error_codes:
			color, cacheable = self.response_error_codes[status_code]
		elif 'other' in self.response_error_codes:
			color, cacheable = self.response_error_codes['other']
		else:
			return None

		transparent = len(color) == 4
		image_opts = ImageOptions(bgcolor=color, transparent=transparent)
		img_source = BlankImageSource(query.size, image_opts, cacheable=cacheable)
		return img_source