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
import json

from functools import reduce
from io import StringIO

from mapproxy.compat import string_type, PY2, BytesIO, iteritems

try:
    from lxml import etree, html

    has_xslt_support = True
    etree, html  # prevent pyflakes warning
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
    info_type = "text"

    def __init__(self, content):
        self.content = content

    def as_string(self):
        return self.content

    @classmethod
    def combine(cls, docs):
        result_content = [doc.as_string() for doc in docs]
        return cls(b"\n".join(result_content))


class XMLFeatureInfoDoc(FeatureInfoDoc):
    info_type = "xml"

    def __init__(self, content):
        if isinstance(content, (string_type, bytes)):
            self._str_content = content
            self._etree = None
        else:
            self._str_content = None
            if hasattr(content, "getroottree"):
                content = content.getroottree()
            self._etree = content
            assert hasattr(content, "getroot"), "expected etree like object"

    def as_string(self):
        if self._str_content is None:
            self._str_content = self._serialize_etree()
        return self._str_content

    def as_etree(self):
        if self._etree is None:
            self._etree = self._parse_content()
        return self._etree

    def _serialize_etree(self):
        return etree.tostring(self._etree)

    def _parse_content(self):
        doc = as_io(self._str_content)
        return etree.parse(doc)

    @classmethod
    def combine(cls, docs):
        if etree is None:
            return TextFeatureInfoDoc.combine(docs)
        doc = docs.pop(0)
        result_tree = copy.deepcopy(doc.as_etree())
        for doc in docs:
            tree = doc.as_etree()
            result_tree.getroot().extend(tree.getroot().iterchildren())

        return cls(result_tree)


class HTMLFeatureInfoDoc(XMLFeatureInfoDoc):
    info_type = "html"

    def _parse_content(self):
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


class JSONFeatureInfoDoc(FeatureInfoDoc):
    info_type = "json"

    def __init__(self, content):
        self.content = content

    def as_string(self):
        return self.content

    @classmethod
    def combine(cls, docs):
        contents = []
        for d in docs:
            content = d.content
            if not isinstance(content, string_type):
                content = content.decode('UTF-8')
            contents.append(json.loads(content))
        combined = reduce(lambda a, b: merge_dict(a, b), contents)
        return cls(json.dumps(combined))


def merge_dict(base, other):
    """
    Return `base` dict with values from `conf` merged in.
    """
    for k, v in iteritems(other):
        if k not in base:
            base[k] = v
        else:
            if isinstance(base[k], dict):
                merge_dict(base[k], v)
            elif isinstance(base[k], list):
                base[k].extend(v)
            else:
                base[k] = v
    return base


def create_featureinfo_doc(content, info_format):
    info_type = featureinfo_type(info_format)
    if info_type == "xml":
        return XMLFeatureInfoDoc(content)
    if info_type == "html":
        return HTMLFeatureInfoDoc(content)
    if info_type == "json":
        return JSONFeatureInfoDoc(content)

    return TextFeatureInfoDoc(content)

def featureinfo_type(info_format):
    info_format = info_format.split(";", 1)[
        0
    ].strip()  # remove mime options like charset
    if info_format in ("text/xml", "application/xml",
                       "application/gml+xml", "application/vnd.ogc.gml"):
        return "xml"
    if info_format == "text/html":
        return "html"
    if info_format == "application/json":
        return "json"

    return "text"


class XSLTransformer(object):

    def __init__(self, xsltscript, info_format=None):
        self.xsltscript = xsltscript
        self.info_type = featureinfo_type(info_format or "text/xml")

    def transform(self, input_doc):
        input_tree = input_doc.as_etree()
        xslt_tree = etree.parse(self.xsltscript)
        transform = etree.XSLT(xslt_tree)
        output_tree = transform(input_tree)
        if self.info_type == "html":
            return HTMLFeatureInfoDoc(output_tree)
        else:
            return XMLFeatureInfoDoc(output_tree)

    __call__ = transform


def as_io(doc):
    if PY2:
        return BytesIO(doc)
    else:
        if isinstance(doc, str):
            return StringIO(doc)
        else:
            return BytesIO(doc)


def combine_docs(docs, transformer=None):
    """
    Combine multiple FeatureInfoDocs.

    Combines as text, if the type of the docs differ.
    Otherwise the type specifix combine is called.

    Returns the combined document and the info_type (text, xml or json).
    info_type is None if the output is transformed, as the type is dependent on the
    transformer.
    """
    if len(set(d.info_type for d in docs)) > 1:
        # more then one info_type, combine as plain text
        doc = TextFeatureInfoDoc.combine(docs)
        infotype = "text"
    else:
        # all same type, combine with type specific handler
        infotype = docs[0].info_type
        doc = docs[0].combine(docs)

        if transformer:
            doc = transformer(doc)
            infotype = None # defined by transformer
    return doc.as_string(), infotype
