class ArcGISClient(object):
    def __init__(self, request_template, http_client = None):
        self.request_template = request_template
        self.http_client = http_client

    def retrieve(self, query, format):
        url  = self._query_url(query, format)
        resp = self.http_client.open(url)
        return resp

    def _query_url(self, query, format):
        req = self.request_template.copy()
        req.params.format = format
        req.params.bbox = query.bbox
        req.params.size = query.size
        req.params.bboxSR = query.srs
        req.params.imageSR = query.srs

        return req.complete_url
