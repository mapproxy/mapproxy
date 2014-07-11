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

from __future__ import with_statement, division
import os

from mapproxy.request.wms import WMS111FeatureInfoRequest, WMS130FeatureInfoRequest
from mapproxy.test.system import module_setup, module_teardown, SystemTest
from mapproxy.test.http import mock_httpd
from mapproxy.test.helper import strip_whitespace

from nose.tools import eq_

test_config = {}


xslt_input = b"""
<xsl:stylesheet version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
 <xsl:template match="/">
   <baz>
     <foo><xsl:value-of select="/a/b/text()" /></foo>
   </baz>
 </xsl:template>
</xsl:stylesheet>""".strip()

xslt_input_html = b"""
<xsl:stylesheet version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
 <xsl:template match="/">
   <baz>
     <foo><xsl:value-of select="/html/body/p" /></foo>
   </baz>
 </xsl:template>
</xsl:stylesheet>""".strip()


xslt_output = b"""
<xsl:stylesheet version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
 <xsl:template match="/">
    <bars>
      <xsl:apply-templates/>
    </bars>
 </xsl:template>

 <xsl:template match="foo">
     <bar><xsl:value-of select="text()" /></bar>
 </xsl:template>
</xsl:stylesheet>""".strip()

xslt_output_html = b"""
<xsl:stylesheet version="1.0"
 xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
 <xsl:template match="/">
    <html>
      <body>
        <h1>Bars</h1>
        <xsl:apply-templates/>
      </body>
    </html>
 </xsl:template>

 <xsl:template match="foo">
     <p><xsl:value-of select="text()" /></p>
 </xsl:template>
</xsl:stylesheet>""".strip()


def setup_module():
    module_setup(test_config, 'xslt_featureinfo.yaml')
    with open(os.path.join(test_config['base_dir'], 'fi_in.xsl'), 'wb') as f:
        f.write(xslt_input)
    with open(os.path.join(test_config['base_dir'], 'fi_in_html.xsl'), 'wb') as f:
        f.write(xslt_input_html)
    with open(os.path.join(test_config['base_dir'], 'fi_out.xsl'), 'wb') as f:
        f.write(xslt_output)
    with open(os.path.join(test_config['base_dir'], 'fi_out_html.xsl'), 'wb') as f:
        f.write(xslt_output_html)
def teardown_module():
    module_teardown(test_config)

TESTSERVER_ADDRESS = 'localhost', 42423

class TestWMSXSLTFeatureInfo(SystemTest):
    config = test_config
    def setup(self):
        SystemTest.setup(self)
        self.common_fi_req = WMS111FeatureInfoRequest(url='/service?',
            param=dict(x='10', y='20', width='200', height='200', layers='fi_layer',
                       format='image/png', query_layers='fi_layer', styles='',
                       bbox='1000,400,2000,1400', srs='EPSG:900913'))

    def test_get_featureinfo(self):
        fi_body = b"<a><b>Bar</b></a>"
        expected_req = ({'path': r'/service_a?LAYERs=a_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913'
                                  '&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=a_one&i=10&J=20&info_format=text/xml'},
                        {'body': fi_body, 'headers': {'content-type': 'text/xml; charset=UTF-8'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            resp = self.app.get(self.common_fi_req)
            eq_(resp.content_type, 'application/vnd.ogc.gml')
            eq_(strip_whitespace(resp.body), b'<bars><bar>Bar</bar></bars>')

    def test_get_featureinfo_130(self):
        fi_body = b"<a><b>Bar</b></a>"
        expected_req = ({'path': r'/service_a?LAYERs=a_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913'
                                  '&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=a_one&i=10&J=20&info_format=text/xml'},
                        {'body': fi_body, 'headers': {'content-type': 'text/xml'}})
        with mock_httpd(('localhost', 42423), [expected_req]):
            req = WMS130FeatureInfoRequest(url='/service?').copy_with_request_params(self.common_fi_req)
            resp = self.app.get(req)
            eq_(resp.content_type, 'text/xml')
            eq_(strip_whitespace(resp.body), b'<bars><bar>Bar</bar></bars>')

    def test_get_multiple_featureinfo(self):
        fi_body1 = b"<a><b>Bar1</b></a>"
        fi_body2 = b"<a><b>Bar2</b></a>"
        fi_body3 = b"<body><h1>Hello<p>Bar3"
        expected_req1 = ({'path': r'/service_a?LAYERs=a_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913'
                                  '&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=a_one&i=10&J=20&info_format=text/xml'},
                        {'body': fi_body1, 'headers': {'content-type': 'text/xml'}})
        expected_req2 = ({'path': r'/service_b?LAYERs=b_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=b_one&X=10&Y=20&info_format=text/xml'},
                        {'body': fi_body2, 'headers': {'content-type': 'text/xml'}})
        expected_req3 = ({'path': r'/service_d?LAYERs=d_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=d_one&X=10&Y=20&info_format=text/html'},
                        {'body': fi_body3, 'headers': {'content-type': 'text/html'}})
        with mock_httpd(('localhost', 42423), [expected_req1, expected_req2, expected_req3]):
            self.common_fi_req.params['layers'] = 'fi_multi_layer'
            self.common_fi_req.params['query_layers'] = 'fi_multi_layer'
            resp = self.app.get(self.common_fi_req)
            eq_(resp.content_type, 'application/vnd.ogc.gml')
            eq_(strip_whitespace(resp.body),
                b'<bars><bar>Bar1</bar><bar>Bar2</bar><bar>Bar3</bar></bars>')

    def test_get_multiple_featureinfo_html_out(self):
        fi_body1 = b"<a><b>Bar1</b></a>"
        fi_body2 = b"<a><b>Bar2</b></a>"
        fi_body3 = b"<body><h1>Hello<p>Bar3"
        expected_req1 = ({'path': r'/service_a?LAYERs=a_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913'
                                  '&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=a_one&i=10&J=20&info_format=text/xml'},
                        {'body': fi_body1, 'headers': {'content-type': 'text/xml'}})
        expected_req2 = ({'path': r'/service_b?LAYERs=b_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=b_one&X=10&Y=20&info_format=text/xml'},
                        {'body': fi_body2, 'headers': {'content-type': 'text/xml'}})
        expected_req3 = ({'path': r'/service_d?LAYERs=d_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=d_one&X=10&Y=20&info_format=text/html'},
                        {'body': fi_body3, 'headers': {'content-type': 'text/html'}})
        with mock_httpd(('localhost', 42423), [expected_req1, expected_req2, expected_req3]):
            self.common_fi_req.params['layers'] = 'fi_multi_layer'
            self.common_fi_req.params['query_layers'] = 'fi_multi_layer'
            self.common_fi_req.params['info_format'] = 'text/html'
            resp = self.app.get(self.common_fi_req)
            eq_(resp.content_type, 'text/html')
            eq_(strip_whitespace(resp.body),
                b'<html><body><h1>Bars</h1><p>Bar1</p><p>Bar2</p><p>Bar3</p></body></html>')

    def test_mixed_featureinfo(self):
        fi_body1 = b"Hello"
        fi_body2 = b"<a><b>Bar2</b></a>"
        expected_req1 = ({'path': r'/service_c?LAYERs=c_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                  '&REQUEST=GetFeatureInfo&HEIGHT=200&SRS=EPSG%3A900913'
                                  '&VERSION=1.1.1&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                  '&WIDTH=200&QUERY_LAYERS=c_one&X=10&Y=20'},
                        {'body': fi_body1, 'headers': {'content-type': 'text/plain'}})
        expected_req2 = ({'path': r'/service_a?LAYERs=a_one&SERVICE=WMS&FORMAT=image%2Fpng'
                                   '&REQUEST=GetFeatureInfo&HEIGHT=200&CRS=EPSG%3A900913'
                                   '&VERSION=1.3.0&BBOX=1000.0,400.0,2000.0,1400.0&styles='
                                   '&WIDTH=200&QUERY_LAYERS=a_one&i=10&J=20&info_format=text/xml'},
                        {'body': fi_body2, 'headers': {'content-type': 'text/xml'}})
        with mock_httpd(('localhost', 42423), [expected_req1, expected_req2]):
            self.common_fi_req.params['layers'] = 'fi_without_xslt_layer,fi_layer'
            self.common_fi_req.params['query_layers'] = 'fi_without_xslt_layer,fi_layer'
            resp = self.app.get(self.common_fi_req)
            eq_(resp.content_type, 'text/plain')
            eq_(strip_whitespace(resp.body),
                b'Hello<baz><foo>Bar2</foo></baz>')