# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

from __future__ import with_statement

import os
import tempfile

from lxml import etree
from nose.tools import eq_

from mapproxy.util.xml import combined_inputs, XSLTransformer
from mapproxy.test.helper import TempFile, strip_whitespace

def test_combined_inputs():
    foo = '<a><b>foo</b></a>'
    bar = '<a><b>bar</b></a>'
    
    result = combined_inputs([foo, bar])
    result = etree.tostring(result)
    eq_(result, '<a><b>foo</b><b>bar</b></a>')
    

class TestXSLTransformer(object):
    def setup(self):
        fd_, self.xsl_script = tempfile.mkstemp('.xsl')
        xsl = """
        <xsl:stylesheet version="1.0"
         xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
         <xsl:template match="/">
            <root>
                <xsl:apply-templates select='/a/b'/>
            </root>
         </xsl:template>
         <xsl:template match="/a/b">
             <foo><xsl:value-of select="text()" /></foo>
         </xsl:template>
        </xsl:stylesheet>""".strip()
        open(self.xsl_script, 'w').write(xsl)
    
    def teardown(self):
        os.remove(self.xsl_script)
        
    def test_transformer(self):
        t = XSLTransformer(self.xsl_script)
        resp = t.transform('<a><b>Text</b></a>')
        eq_(strip_whitespace(resp), '<root><foo>Text</foo></root>')


    def test_multiple(self):
        t = XSLTransformer(self.xsl_script)
        resp = t.transform(
            ['<a><b>ab</b></a>', 
             '<a><b>ab1</b><b>ab2</b><b>ab3</b></a>',
             '<a><b>ab1</b><c>ac</c><b>ab2</b></a>',
        ])
        eq_(strip_whitespace(resp), 
            strip_whitespace('''
            <root>
              <foo>ab</foo>
              <foo>ab1</foo><foo>ab2</foo><foo>ab3</foo>
              <foo>ab1</foo><foo>ab2</foo>
            </root>'''))
        

if __name__ == '__main__':
    test_xstltransformer()