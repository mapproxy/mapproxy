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

from codecs import decode
import copy
import json

from functools import reduce
from io import StringIO, BytesIO
from typing import Optional, Union

from lxml import etree, html


class FeatureInfoDoc(object):
    content_type = None
    content: Union[None, str, bytes] = None

    def as_etree(self):
        raise NotImplementedError()

    def as_string(self):
        raise NotImplementedError()


class TextFeatureInfoDoc(FeatureInfoDoc):
    info_type = "text"

    def __init__(self, content: Union[str, bytes]):
        self.content = content

    def as_string(self) -> str:
        if isinstance(self.content, str):
            return self.content
        else:
            return decode(self.content)  # type: ignore[arg-type]

    @classmethod
    def combine(cls, docs: list[FeatureInfoDoc]):
        result_content = [doc.as_string() for doc in docs]
        return cls("\n".join(result_content))


class XMLFeatureInfoDoc(FeatureInfoDoc):
    info_type = "xml"
    defaultEncoding = "UTF-8"
    _etree: Optional[etree._ElementTree] = None

    def __init__(self, content: Union[str, bytes]):
        if isinstance(content, (str, bytes)):
            self.content = content
        else:
            if hasattr(content, "getroottree"):
                content = content.getroottree()
            self._etree = content
            assert hasattr(content, "getroot"), "expected etree like object"

    def as_string(self):
        if self.content is None:
            self.content = self._serialize_etree()
        if isinstance(self.content, str):
            return self.content
        else:
            return decode(self.content)  # type: ignore[arg-type]

    def as_etree(self):
        if self._etree is None:
            self._etree = self._parse_content()
        return self._etree

    def _serialize_etree(self) -> Union[str, bytes]:
        _etree = self.as_etree()
        encoding = _etree.docinfo.encoding if \
            _etree.docinfo.encoding else self.defaultEncoding
        as_string = etree.tostring(_etree, encoding=encoding, xml_declaration=False)
        return decode(as_string, encoding)  # type: ignore[arg-type]

    def _parse_content(self):
        if isinstance(self.content, str) and self.content.lstrip().startswith('<?xml'):
            # Convert back to bytes if it has XML declaration
            return etree.parse(BytesIO(self.content.encode('utf-8')))
        elif isinstance(self.content, str):
            return etree.parse(StringIO(self.content))
        else:
            return etree.parse(BytesIO(self.content))

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
        root = html.document_fromstring(self.content)
        return root

    def _serialize_etree(self):
        encoding = self._etree.docinfo.encoding if \
            self._etree.docinfo.encoding else self.defaultEncoding
        return decode(html.tostring(self._etree, encoding=encoding), encoding)

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
        return self.content if isinstance(self.content, str) else decode(self.content)

    @classmethod
    def combine(cls, docs):
        contents = []
        for d in docs:
            result = json.loads(d.content)
            if result:
                contents.append(result)
        if not contents:
            return cls(json.dumps({}))
        combined = reduce(lambda a, b: merge_dict(a, b), contents)
        return cls(json.dumps(combined))


def merge_dict(base, other):
    """
    Return `base` dict with values from `conf` merged in.
    """
    for k, v in other.items():
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


def combine_docs(docs, transformer=None):
    """
    Combine multiple FeatureInfoDocs.

    Combines as text, if the type of the docs differ.
    Otherwise, the type specific combine is called.

    Returns the combined document and the info_type (text, xml or json).
    info_type is None if the output is transformed, as the type is dependent on the
    transformer.
    """
    if len(set(d.info_type for d in docs)) > 1:
        # more than one info_type, combine as plain text
        doc = TextFeatureInfoDoc.combine(docs)
        infotype = "text"
    else:
        # all same type, combine with type specific handler
        infotype = docs[0].info_type
        doc = docs[0].combine(docs)

        if transformer:
            doc = transformer(doc)
            infotype = None  # defined by transformer
    return doc.as_string(), infotype
