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
		img_source = BlankImageSource(query.size, image_opts)
		img_source.cacheable = cacheable
		return img_source