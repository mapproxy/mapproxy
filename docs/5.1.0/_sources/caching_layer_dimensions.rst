Caching Dimensions
##################

WMS servers have the capability to offer layers with 1..n dimensions.  A WMS
layer may provide dimensions such as time, elevation or other axes to be able
to visualize maps of multidimensional data.  The `OGC OGC Best Practice for
using Web Map Services (WMS) with Time-Dependent or Elevation-Dependent Data`_
is an example typically implemented by WMS providers of multidimensional
data.

MapProxy supports caching layers with dimensions and making them available
through standard WMS mechanisms.

Configuration
=============

To enable dimension caching, the underlying WMS layer must have dimensions
defined and available.  The following properties are required in configuration
to successfully cache any layer with dimensions:

- ``forward_req_params``: list of 1..n query parameter names to send when
  caching the layer, if request by the MapProxy client.  This property is
  specified in a source
- ``dimensions``: an object of 1..n keys of dimension definitions. The
  dimension names must match with those specified in ``forward_req_params``
  for a given layer/source combination.  Each dimension object requires
  a default dimension (in cases where not specified by the client) as well
  as a list of dimension values.  Dimension lists can be intervals, or a
  a compound value of ``start-date-time/end-date-time/duration``

An example is shown below:

.. code-block:: yaml

   sources:
        test:
          type: wms
          req:
            url: https://example.org/wms
            layers: global-air-temperature-15km
          forward_req_params:
            - time
            - dim_reference_time

.. code-block:: yaml

        layers:
          - name: global-air-temperature-15km
            title: Global Air Temperature (°C) - 15km
            sources: [test_cache]
            dimensions:
              time:
                values:
                  - "2020-09-22T11:20:00Z/2020-09-22T14:20:00Z/PT2H"
                default: "2020-09-22T14:20:00Z"
              dim_reference_time:
                values:
                  - "2020-09-22T11:20:00Z/2020-09-22T14:20:00Z/PT2H"
                default: "2020-09-22T14:20:00Z"


ISO 8601 Interval
=================

For example:
         ``2020-03-25T12:00:00Z/2020-03-27T00:00:00Z/PT12H30M``

A time interval is the intervening time between two time points. The amount of intervening time is expressed by a duration (as described in the previous section). The two time points (start and end) are expressed by either a combined date and time representation or just a date representation.

There are four ways to express a time interval:
        1. Start and end, such as "2007-03-01T13:00:00Z/2008-05-11T15:30:00Z"
        2. Start and duration, such as "2007-03-01T13:00:00Z/P1Y2M10DT2H30M"
        3. Duration and end, such as "P1Y2M10DT2H30M/2008-05-11T15:30:00Z"
        4. Duration only, such as "P1Y2M10DT2H30M", with additional context information

        P is the duration designator (for period) placed at the start of the duration representation.
           - Y is the year designator that follows the value for the number of years.
           - M is the month designator that follows the value for the number of months.
           - W is the week designator that follows the value for the number of weeks.
           - D is the day designator that follows the value for the number of days.
        T is the time designator that precedes the time components of the representation.
           - H is the hour designator that follows the value for the number of hours.
           - M is the minute designator that follows the value for the number of minutes.
           - S is the second designator that follows the value for the number of seconds.
         
WMS Capabilities
================

The following is an example of the resulting WMS capabilities in MapProxy:

.. code-block:: xml

        <?xml version="1.0"?>
        <WMS_Capabilities xmlns="http://www.opengis.net/wms" xmlns:sld="http://www.opengis.net/sld" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.3.0" xsi:schemaLocation="http://www.opengis.net/wms http://schemas.opengis.net/wms/1.3.0/capabilities_1_3_0.xsd http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/sld_capabilities.xsd">
          <Service>
            <Name>WMS</Name>
            <Title>Test Dimension</Title>
            <Abstract/>
            <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="http://127.0.0.1:8080/service"/>
            <Fees>none</Fees>
            <AccessConstraints>none</AccessConstraints>
            <MaxWidth>4000</MaxWidth>
            <MaxHeight>4000</MaxHeight>
          </Service>
          <Capability>
            <Request>
              <GetCapabilities>
                <Format>text/xml</Format>
                <DCPType>
                  <HTTP>
                    <Get>
                      <OnlineResource xlink:href="http://127.0.0.1:8080/service?"/>
                    </Get>
                  </HTTP>
                </DCPType>
              </GetCapabilities>
              <GetMap>
                <Format>image/png</Format>
                <Format>image/jpeg</Format>
                <Format>image/gif</Format>
                <Format>image/GeoTIFF</Format>
                <Format>image/tiff</Format>
                <DCPType>
                  <HTTP>
                    <Get>
                      <OnlineResource xlink:href="http://127.0.0.1:8080/service?"/>
                    </Get>
                  </HTTP>
                </DCPType>
              </GetMap>
              <GetFeatureInfo>
                <Format>text/plain</Format>
                <Format>text/html</Format>
                <Format>text/xml</Format>
                <DCPType>
                  <HTTP>
                    <Get>
                      <OnlineResource xlink:href="http://127.0.0.1:8080/service?"/>
                    </Get>
                  </HTTP>
                </DCPType>
              </GetFeatureInfo>
            </Request>
            <Exception>
              <Format>XML</Format>
              <Format>INIMAGE</Format>
              <Format>BLANK</Format>
            </Exception>
            <Layer>
              <Name>global-air-temperature-15km</Name>
              <Title>Global Air Temperature (°C) - 15km</Title>
              <CRS>EPSG:4326</CRS>
              <CRS>EPSG:3857</CRS>
              <EX_GeographicBoundingBox>
                <westBoundLongitude>-180</westBoundLongitude>
                <eastBoundLongitude>180</eastBoundLongitude>
                <southBoundLatitude>-89.999999</southBoundLatitude>
                <northBoundLatitude>89.999999</northBoundLatitude>
              </EX_GeographicBoundingBox>
              <BoundingBox CRS="CRS:84" minx="-180" miny="-89.999999" maxx="180" maxy="89.999999"/>
              <BoundingBox CRS="EPSG:4326" minx="-90.0" miny="-180.0" maxx="90.0" maxy="180.0"/>
              <BoundingBox CRS="EPSG:3857" minx="-20037508.342789244" miny="-147730762.66992167" maxx="20037508.342789244" maxy="147730758.19456753"/>
              <Dimension name="time" default="2020-09-22T14:20:00Z" nearestValue="0" units="ISO8601">2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z</Dimension>
              <Dimension name="dim_reference_time" default="2020-09-22T14:20:00Z" nearestValue="0" units="ISO8601">2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z</Dimension>
            </Layer>
          </Capability>
        </WMS_Capabilities>


Known limitations
=================

- some WMS time-enabled servers provide dimension support for real-time
  data with ongoing updates to retention time.  In this case, a given
  WMS layer's temporal extent may be updated a few hours after, for
  example.  It is up to the MapProxy configuration to manage dimensions/
  extents accordingly.  This can be done with custom scripts
  to run WMS ``GetCapabilities`` requests and write the updated temporal
  dimensions into the MapProxy configuration.  An example of such a tool
  is `geomet-mapproxy`_
- caches of layers with dimensions need to be cleaned/deleted by the MapProxy
  administrator.  This can typically be done via cron/schedule accordingly
- dimemsion support is only implemented in the default file cache backend
  at this time


Tests
=====

All tests related to caching layer dimensions: ``mapproxy/test/system/test_dimensions.py``

.. _`OGC OGC Best Practice for using Web Map Services (WMS) with Time-Dependent or Elevation-Dependent Data`: https://portal.ogc.org/files/?artifact_id=56394
.. _`geomet-mapproxy`: https://github.com/ECCC-MSC/geomet-mapproxy
