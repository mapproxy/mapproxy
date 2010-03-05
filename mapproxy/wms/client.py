from mapproxy.core.image import ImageSource
from mapproxy.core.client import retrieve_image, retrieve_url
from mapproxy.core.srs import SRS, make_lin_transf

class WMSClient(object):
    """
    Client for WMS requests.
    """
    def __init__(self, request_template=None, client_request=None):
        """
        :param request_template: a request that will be used as a template for
            new requests
        :param client_request: function is called for each client request.
            gets the request_template and the according request. should return
            a new request object that is used for this request. 
        """
        if client_request is None:
            client_request = wms_client_request
        self.client_request = client_request
        self.request_template = request_template

    def get_map(self, request):
        resp = retrieve_image(self._map_url(request))
        return ImageSource(resp, request.params.format)
    
    def _map_url(self, request):
        req = self.client_request(self.request_template, request)
        return req.complete_url
    
    def get_info(self, request):
        resp = retrieve_url(self._info_url(request))
        return resp.read()
    
    def _info_url(self, request):
        req = self.client_request(self.request_template, request)

        if self.request_template is None:
            return req.complete_url
        
        req.params['srs'] = request.params['srs'] #restore requested srs
        self._transform_fi_request(req)
        req.params['query_layers'] = req.params['layers']
        return req.complete_url
    
    def _transform_fi_request(self, request):
        params = request.params
        if self.request_template.params.srs == params.srs:
            return request
        
        pos = params.pos
        req_bbox = params.bbox
        req_pos = make_lin_transf((0, 0) + params.size, req_bbox)(pos)
        req_srs = SRS(params.srs)
        dst_srs = SRS(self.request_template.params.srs)
        dst_pos = req_srs.transform_to(dst_srs, req_pos)
        dst_bbox = req_srs.transform_bbox_to(dst_srs, req_bbox)
        dst_pos = make_lin_transf((dst_bbox), (0, 0) + params.size)(dst_pos)
        
        params['srs'] = self.request_template.params.srs
        params.bbox = dst_bbox
        params.pos = dst_pos
        

def wms_client_request(request_template, map_request):
    if request_template is None:
        return map_request.copy()
    req = request_template.copy_with_request_params(map_request)
    req.url = request_template.url
    req.params.bbox = map_request.params.bbox
    return req
