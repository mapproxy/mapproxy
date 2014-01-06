from functools import partial as fp
from mapproxy.request.base import RequestParams, BaseRequest, split_mime_type


class ArcGISExportRequestParams(RequestParams):
    """
    Supported params f, bbox(required), size, dpi, imageSR, bboxSR, format, layerDefs,
    layers, transparent, time, layerTimeOptions.

    @param layers: Determines which layers appear on the exported map. There are
                   four ways to specify layers: show, hide, include, exclude.
                   (ex show:1,2)
    """
    def _get_format(self):
        """
        The requested format as string (w/o any 'image/', 'text/', etc prefixes)
        """
        return self["format"]
    def _set_format(self, format):
        self["format"] = format.rsplit("/")[-1]
    format = property(_get_format, _set_format)
    del _get_format
    del _set_format

    def _get_bbox(self):
        """
        ``bbox`` as a tuple (minx, miny, maxx, maxy).
        """
        if 'bbox' not in self.params or self.params['bbox'] is None:
            return None
        points = map(float, self.params['bbox'].split(','))
        return tuple(points[:4])
    def _set_bbox(self, value):
        if value is not None and not isinstance(value, basestring):
            value = ','.join(str(x) for x in value)
        self['bbox'] = value
    bbox = property(_get_bbox, _set_bbox)
    del _get_bbox
    del _set_bbox

    def _get_size(self):
        """
        Size of the request in pixel as a tuple (width, height),
        or None if one is missing.
        """
        if 'size' not in self.params or self.params['size'] is None:
            return None
        dim = map(float, self.params['size'].split(','))
        return tuple(dim[:2])
    def _set_size(self, value):
        if value is not None and not isinstance(value, basestring):
            value = ','.join(str(x) for x in value)
        self['size'] = value
    size = property(_get_size, _set_size)
    del _get_size
    del _set_size

    def _get_srs(self, key):
        return self.params.get(key, None)
    def _set_srs(self, srs, key):
        if hasattr(srs, 'srs_code'):
            code = srs.srs_code
        else:
            code = srs
        self.params[key] = code.rsplit(":", 1)[-1]

    bboxSR = property(fp(_get_srs, key = "bboxSR"), fp(_set_srs, key = "bboxSR"))
    imageSR = property(fp(_get_srs, key = "imageSR"), fp(_set_srs, key = "imageSR"))
    del _get_srs
    del _set_srs


class ArcGISRequest(BaseRequest):
    request_params = ArcGISExportRequestParams
    fixed_params = {"f": "image"}

    def __init__(self, param=None, url='', validate=False, http=None):
        BaseRequest.__init__(self, param, url, validate, http)

        self.url = self.url.rstrip("/")
        if not self.url.endswith("export"):
            self.url += "/export"

    def copy(self):
        return self.__class__(param=self.params.copy(), url=self.url)

    @property
    def query_string(self):
        params = self.params.copy()
        for key, value in self.fixed_params.iteritems():
            params[key] = value
        return params.query_string


def create_request(req_data, param):
    req_data = req_data.copy()

    # Pop the URL off the request data.
    url = req_data['url']
    del req_data['url']

    if 'format' in param:
        req_data['format'] = param['format']

    if 'transparent' in req_data:
        # Convert boolean to a string.
        req_data['transparent'] = str(req_data['transparent'])

    return ArcGISRequest(url = url, param = req_data)
