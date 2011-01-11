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
from cStringIO import StringIO
from lxml import etree

class XSLTransformer(object):
    def __init__(self, xslscript):
        self.xslscript = xslscript
    
    def transform(self, input_docs):
        if isinstance(input_docs, list):
            input_tree = combined_inputs(input_docs)
        else:
            input_tree = etree.parse(StringIO(input_docs))
        
        xslt_tree = etree.parse(self.xslscript)
        
        transform = etree.XSLT(xslt_tree)
        
        output_tree = transform(input_tree)
        
        result = etree.tostring(output_tree, pretty_print=True)
        return result
    
    __call__ = transform


def combined_inputs(input_docs):
    doc = input_docs.pop(0)
    input_tree = etree.parse(StringIO(doc))
    for doc in input_docs:
        doc_tree = etree.parse(StringIO(doc))
        input_tree.getroot().extend(doc_tree.getroot().iterchildren())
    return input_tree
