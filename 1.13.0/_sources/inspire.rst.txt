.. _inpire:

.. highlight:: yaml

INSPIRE View Service
====================

MapProxy can act as an INSPIRE View Service. A View Service is a WMS 1.3.0 with an extended capabilities document.

.. versionadded:: 1.8.1


INSPIRE Metadata
----------------

A View Service can either link to an existing metadata document or it can embed the service and layer metadata.
These two options are described as Scenario 1 and 2 in the Technical Guidance document.

Linked Metadata
^^^^^^^^^^^^^^^

Scenario 1 uses links to existing INSPIRE Discovery Services (CSW). You can link to metadata documents for the service and each layer.

For services you need to use the ``inspire_md`` block inside ``services.wms`` with ``type: linked``.
For example::

    services:
      wms:
        md:
          title: Example INSPIRE View Service
        inspire_md:
          type: linked
          metadata_url:
            media_type: application/vnd.iso.19139+xml
            url: http://example.org/csw/doc
          languages:
            default: eng


The View Services specification uses the WMS 1.3.0 extended capabilities for the layers metadata.
Refer to the :ref:`layers metadata documentation<layer_metadata>`.

For example::

    layers:
      - name: example_layer
        title: Example Layer
        md:
          metadata:
           - url:    http://example.org/csw/layerdoc
             type:   ISO19115:2003
             format: text/xml

Embedded Metadata
^^^^^^^^^^^^^^^^^

Scenario 2 embeds the metadata directly into the capabilities document.
Some metadata elements are mapped to an equivalent element in the WMS capabilities. The Resource Title is set with the normal `title` option for example. Other elements need to be configured inside the ``inspire_md`` block with ``type: embedded``.

Here is a full example::

    services:
      wms:
        md:
          title: Example INSPIRE View Service
          abstract: This is an example service with embedded INSPIRE metadata.
          online_resource: http://example.org/
          contact:
            person: Your Name Here
            position: Technical Director
            organization: Acme Inc.
            address: Fakestreet 123
            city: Somewhere
            postcode: 12345
            country: Germany
            phone: +49(0)000-000000-0
            fax: +49(0)000-000000-0
            email: info@example.org
          access_constraints: constraints
          fees: 'None'
          keyword_list:
            - vocabulary: GEMET
              keywords:   [Orthoimagery]

        inspire_md:
          type: embedded
          resource_locators:
            - url: http://example.org/metadata
              media_type: application/vnd.iso.19139+xml
          temporal_reference:
            date_of_creation: 2015-05-01
          metadata_points_of_contact:
            - organisation_name: Acme Inc.
              email: acme@example.org
          conformities:
            - title:
                COMMISSION REGULATION (EU) No 1089/2010 of 23 November 2010 implementing Directive 2007/2/EC of the European Parliament and of the Council as regards interoperability of spatial data sets and services
              date_of_publication: 2010-12-08
              uris:
                - OJ:L:2010:323:0011:0102:EN:PDF
              resource_locators:
              - url: http://eur-lex.europa.eu/LexUriServ/LexUriServ.do?uri=OJ:L:2010:323:0011:0102:EN:PDF
                media_type: application/pdf
              degree: notEvaluated
          mandatory_keywords:
            - infoMapAccessService
            - humanGeographicViewer
          keywords:
            - title: GEMET - INSPIRE themes
              date_of_last_revision: 2008-06-01
              keyword_value: Orthoimagery
          metadata_date: 2015-07-23
          metadata_url:
            media_type: application/vnd.iso.19139+xml
            url: http://example.org/csw/doc


You can express all dates as either ``date_of_creation``, ``date_of_publication`` or ``date_of_last_revision``.

The View Services specification uses the WMS 1.3.0 extended capabilities for the layers metadata.
Refer to the :ref:`layers metadata documentation<layer_metadata>` for all available options.

For example::

    layers:
      - name: example_layer
        title: Example Layer
        legendurl: http://example.org/example_legend.png
        md:
          abstract: Some abstract
          keyword_list:
            - vocabulary: GEMET
              keywords:   [Orthoimagery]
          metadata:
           - url:    http://example.org/csw/layerdoc
             type:   ISO19115:2003
             format: text/xml
          identifier:
           - url:    http://www.example.org
             name:   example.org
             value:  "http://www.example.org#cf3c8572-601f-4f47-a922-6c67d388d220"


Languages
---------

A View Service always needs to indicate the language of the layer names, abstracts, map labels, etc..
You can only configure a single language as MapProxy does not support multi-lingual configurations.
You need to set the default language as a `ISO 639-2/alpha-3 <https://www.loc.gov/standards/iso639-2/php/code_list.php>`_ code:

::

    inspire_md:
      languages:
        default: eng
      ....

