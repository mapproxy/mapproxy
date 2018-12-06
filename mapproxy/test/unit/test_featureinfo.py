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

import os
import tempfile

from lxml import etree, html

from mapproxy.featureinfo import (
    XSLTransformer,
    TextFeatureInfoDoc,
    XMLFeatureInfoDoc,
    HTMLFeatureInfoDoc,
    JSONFeatureInfoDoc,
    combine_docs,
)
from mapproxy.test.helper import strip_whitespace


class TestXSLTransformer(object):

    def setup(self):
        fd, self.xsl_script = tempfile.mkstemp(".xsl")
        os.close(fd)
        xsl = (
            b"""
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
        )
        with open(self.xsl_script, "wb") as f:
            f.write(xsl)

    def teardown(self):
        os.remove(self.xsl_script)

    def test_transformer(self):
        t = XSLTransformer(self.xsl_script)
        doc = t.transform(XMLFeatureInfoDoc("<a><b>Text</b></a>"))
        assert strip_whitespace(doc.as_string()) == b"<root><foo>Text</foo></root>"

    def test_multiple(self):
        t = XSLTransformer(self.xsl_script)
        doc = t.transform(
            XMLFeatureInfoDoc.combine(
                [
                    XMLFeatureInfoDoc(x)
                    for x in [
                        b"<a><b>ab</b></a>",
                        b"<a><b>ab1</b><b>ab2</b><b>ab3</b></a>",
                        b"<a><b>ab1</b><c>ac</c><b>ab2</b></a>",
                    ]
                ]
            )
        )
        assert strip_whitespace(doc.as_string()) == strip_whitespace(
            b"""
            <root>
              <foo>ab</foo>
              <foo>ab1</foo><foo>ab2</foo><foo>ab3</foo>
              <foo>ab1</foo><foo>ab2</foo>
            </root>"""
        )
        assert doc.info_type == "xml"


class TestXMLFeatureInfoDocs(object):

    def test_as_string(self):
        input_tree = etree.fromstring("<root></root>")
        doc = XMLFeatureInfoDoc(input_tree)
        assert strip_whitespace(doc.as_string()) == b"<root/>"

    def test_as_etree(self):
        doc = XMLFeatureInfoDoc("<root>hello</root>")
        assert doc.as_etree().getroot().text == "hello"

    def test_combine(self):
        docs = [
            XMLFeatureInfoDoc("<root><a>foo</a></root>"),
            XMLFeatureInfoDoc("<root><b>bar</b></root>"),
            XMLFeatureInfoDoc("<other_root><a>baz</a></other_root>"),
        ]
        result = XMLFeatureInfoDoc.combine(docs)

        assert strip_whitespace(result.as_string()) == strip_whitespace(
            b"<root><a>foo</a><b>bar</b><a>baz</a></root>"
        )
        assert result.info_type == "xml"


class TestXMLFeatureInfoDocsNoLXML(object):

    def setup(self):
        from mapproxy import featureinfo

        self.old_etree = featureinfo.etree
        featureinfo.etree = None

    def teardown(self):
        from mapproxy import featureinfo

        featureinfo.etree = self.old_etree

    def test_combine(self):
        docs = [
            XMLFeatureInfoDoc(b"<root><a>foo</a></root>"),
            XMLFeatureInfoDoc(b"<root><b>bar</b></root>"),
            XMLFeatureInfoDoc(b"<other_root><a>baz</a></other_root>"),
        ]
        result = XMLFeatureInfoDoc.combine(docs)

        assert (
            b"<root><a>foo</a></root>\n<root><b>bar</b></root>\n<other_root><a>baz</a></other_root>"
            == result.as_string()
        )
        assert result.info_type == "text"


class TestHTMLFeatureInfoDocs(object):

    def test_as_string(self):
        input_tree = html.fromstring("<p>Foo")
        doc = HTMLFeatureInfoDoc(input_tree)
        assert b"<body><p>Foo</p></body>" in strip_whitespace(doc.as_string())

    def test_as_etree(self):
        doc = HTMLFeatureInfoDoc("<p>hello</p>")
        assert doc.as_etree().find("body/p").text == "hello"

    def test_combine(self):
        docs = [
            HTMLFeatureInfoDoc(b"<html><head><title>Hello<body><p>baz</p><p>baz2"),
            HTMLFeatureInfoDoc(b"<p>foo</p>"),
            HTMLFeatureInfoDoc(b"<body><p>bar</p></body>"),
        ]
        result = HTMLFeatureInfoDoc.combine(docs)
        assert b"<title>Hello</title>" in result.as_string()
        assert (
            b"<body><p>baz</p><p>baz2</p><p>foo</p><p>bar</p></body>"
            in result.as_string()
        )
        assert result.info_type == "html"

    def test_combine_parts(self):
        docs = [
            HTMLFeatureInfoDoc("<p>foo</p>"),
            HTMLFeatureInfoDoc("<body><p>bar</p></body>"),
            HTMLFeatureInfoDoc("<html><head><title>Hello<body><p>baz</p><p>baz2"),
        ]
        result = HTMLFeatureInfoDoc.combine(docs)

        assert (
            b"<body><p>foo</p><p>bar</p><p>baz</p><p>baz2</p></body>"
            in result.as_string()
        )
        assert result.info_type == "html"


class TestHTMLFeatureInfoDocsNoLXML(object):

    def setup(self):
        from mapproxy import featureinfo

        self.old_etree = featureinfo.etree
        featureinfo.etree = None

    def teardown(self):
        from mapproxy import featureinfo

        featureinfo.etree = self.old_etree

    def test_combine(self):
        docs = [
            HTMLFeatureInfoDoc(b"<html><head><title>Hello<body><p>baz</p><p>baz2"),
            HTMLFeatureInfoDoc(b"<p>foo</p>"),
            HTMLFeatureInfoDoc(b"<body><p>bar</p></body>"),
        ]
        result = HTMLFeatureInfoDoc.combine(docs)

        assert (
            b"<html><head><title>Hello<body><p>baz</p>"
            b"<p>baz2\n<p>foo</p>\n<body><p>bar</p></body>" == result.as_string()
        )
        assert result.info_type == "text"


class TestJSONFeatureInfoDocs(object):

    def test_combine(self):
        docs = [
            JSONFeatureInfoDoc("{}"),
            JSONFeatureInfoDoc('{"results": [{"foo": 1}]}'),
            JSONFeatureInfoDoc('{"results": [{"bar": 2}]}'),
        ]
        result = JSONFeatureInfoDoc.combine(docs)

        assert """{"results": [{"foo": 1}, {"bar": 2}]}""" == result.as_string()
        assert result.info_type == "json"


class TestCombineDocs(object):

    def test_combine_json(self):
        docs = [
            JSONFeatureInfoDoc("{}"),
            JSONFeatureInfoDoc('{"results": [{"foo": 1}]}'),
            JSONFeatureInfoDoc('{"results": [{"bar": 2}]}'),
        ]
        result, infotype = combine_docs(docs, None)

        assert """{"results": [{"foo": 1}, {"bar": 2}]}""" == result
        assert infotype == "json"

    def test_combine_xml(self):
        docs = [
            XMLFeatureInfoDoc("<root><a>foo</a></root>"),
            XMLFeatureInfoDoc("<root><b>bar</b></root>"),
        ]
        result, infotype = combine_docs(docs, None)

        assert b"""<root><a>foo</a><b>bar</b></root>""" == result
        assert infotype == "xml"

    def test_combine_transform_xml(self, tmpdir):
        xsl = tmpdir.join("transform.xsl")
        xsl.write(
            """<xsl:stylesheet version="1.0"
         xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
         <xsl:template match="/">
            <root>
                <xsl:apply-templates select='/a/b'/>
            </root>
         </xsl:template>
         <xsl:template match="/a/b">
             <foo><xsl:value-of select="text()" /></foo>
         </xsl:template>
        </xsl:stylesheet>
        """
        )
        transf = XSLTransformer(xsl.strpath)
        docs = [
            XMLFeatureInfoDoc("<a><b>foo1</b></a>"),
            XMLFeatureInfoDoc("<a><b>foo2</b></a>"),
        ]
        result, infotype = combine_docs(docs, transf)

        assert b"""<root><foo>foo1</foo><foo>foo2</foo></root>""" == result
        assert infotype is None

    def test_combine_mixed(self):
        docs = [
            JSONFeatureInfoDoc(b'{"results": [{"foo": 1}]}'),
            TextFeatureInfoDoc(b"Plain Text"),
        ]
        result, infotype = combine_docs(docs, None)

        assert b"""{"results": [{"foo": 1}]}\nPlain Text""" == result
        assert infotype == "text"
