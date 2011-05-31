# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
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

import copy
from cStringIO import StringIO

try:
    from lxml import etree, html
    has_xslt_support = True
    etree, html # prevent pyflakes warning
except ImportError:
    has_xslt_support = False
    etree = html = None

class FeatureInfoDoc(object):
    content_type = None
    
    def as_etree(self):
        raise NotImplementedError()
    
    def as_string(self):
        raise NotImplementedError()
    

class TextFeatureInfoDoc(FeatureInfoDoc):
    info_type = 'text'
    
    def __init__(self, content):
        self.content = content
    
    def as_string(self):
        return self.content
    
    @classmethod
    def combine(cls, docs):
        result_content = [doc.as_string() for doc in docs]
        return cls('\n'.join(result_content))

class XMLFeatureInfoDoc(FeatureInfoDoc):
    info_type = 'xml'
    
    def __init__(self, content):
        if isinstance(content, basestring):
            self._str_content = content
            self._etree = None
        else:
            self._str_content = None
            if hasattr(content, 'getroottree'):
                content = content.getroottree()
            self._etree = content
            assert hasattr(content, 'getroot'), "expected etree like object"
    
    def as_string(self):
        if self._str_content is None:
            self._str_content = self._serialize_etree()
        return self._str_content
    
    def as_etree(self):
        if self._etree is None:
            self._etree = self._parse_str_content()
        return self._etree
    
    def _serialize_etree(self):
        return etree.tostring(self._etree)
    
    def _parse_str_content(self):
        doc = StringIO(self._str_content)
        return etree.parse(doc)
    
    @classmethod
    def combine(cls, docs):
        if etree is None: return TextFeatureInfoDoc.combine(docs)
        doc = docs.pop(0)
        result_tree = copy.deepcopy(doc.as_etree())
        for doc in docs:
            tree = doc.as_etree()
            result_tree.getroot().extend(tree.getroot().iterchildren())
        
        return cls(result_tree)

class HTMLFeatureInfoDoc(XMLFeatureInfoDoc):
    info_type = 'html'
    
    def _parse_str_content(self):
        root = html.document_fromstring(self._str_content)
        return root
    
    def _serialize_etree(self):
        return html.tostring(self._etree)
    
    @classmethod
    def combine(cls, docs):
        if etree is None:
            return TextFeatureInfoDoc.combine(docs)
        
        doc = docs.pop(0)
        result_tree = copy.deepcopy(doc.as_etree())

        for doc in docs:
            tree = doc.as_etree()
            
            try:
                body = tree.body.getchildren()
            except IndexError:
                body = tree.getchildren()
            result_tree.body.extend(body)

        return cls(result_tree)

def create_featureinfo_doc(content, info_format):
    if info_format in ('text/xml', 'application/vnd.ogc.gml'):
        return XMLFeatureInfoDoc(content)
    if info_format == 'text/html':
        return HTMLFeatureInfoDoc(content)
    
    return TextFeatureInfoDoc(content)
    

class XSLTransformer(object):
    def __init__(self, xsltscript):
        self.xsltscript = xsltscript
    
    def transform(self, input_doc):
        input_tree = input_doc.as_etree()
        xslt_tree = etree.parse(self.xsltscript)
        transform = etree.XSLT(xslt_tree)
        output_tree = transform(input_tree)
        return XMLFeatureInfoDoc(output_tree)
    
    __call__ = transform

def combined_inputs(input_docs):
    doc = input_docs.pop(0)
    input_tree = etree.parse(StringIO(doc))
    for doc in input_docs:
        doc_tree = etree.parse(StringIO(doc))
        input_tree.getroot().extend(doc_tree.getroot().iterchildren())
    return input_tree
