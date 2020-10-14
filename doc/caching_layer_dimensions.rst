Caching Dimensions
##################

MapProxy allows to cache layers with dimensions such as elevation/level, timestamp, etc. 



Configuration
=============


Config file yaml follows the usual mapproxy configuration, however ``forward_req_params`` and ``dimensions`` are necessary to cache successfully any layer. For example: 

::

        
   sources:
        test:
          type: wms
          req:
            url: https://example.url/geomet/?
            layers: Layer_Test
          forward_req_params: ["time","dim_reference_time"]
          

::

        
        layers:
          - name: Layer_Test
            title: Layer_Test - Dimension
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


ISO8601 Interval
================
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
         
WMS CAPABILITIES
================

The following is an example of WMS capabilities 

::

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
        <Name>Layer_Test</Name>
        <Title>Layer_Test - Dimension</Title>
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
        <Dimension name="time" default="2020-09-22T14:20:00Z" nearestValue="0" units="ISO8601">
        2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z
        </Dimension>
        <Dimension name="dim_reference_time" default="2020-09-22T14:20:00Z" nearestValue="0" units="ISO8601">
        2020-09-22T11:20:00Z,2020-09-22T13:20:00Z,2020-09-22T15:20:00Z
        </Dimension>
        </Layer>
        </Capability>
        </WMS_Capabilities>


Test
====

All tests related to caching layer dimensions: ``mapproxy/test/system/test_dimensions.py``