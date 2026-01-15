This diagram visualizes a WMTS request for a cache source that requests a WMS.


Request:

```bash
rm -rf ../../apps/base/cache_data/basemap_cache_EPSG3857/
curl -X GET --location "http://localhost:8080/wmts/basemap/GLOBAL_WEBMERCATOR/11/1079/660.png"
```


Configuration:

```yaml
services:
  wmts:
    restful: true

layers:
  - name: basemap
    title: basemap
    sources: [basemap_cache]

caches:
  basemap_cache:
    grids: [GLOBAL_WEBMERCATOR]
    sources: [basemap_wms]

sources:
  basemap_wms:
    type: wms
    req:
      url: https://sgx.geodatenzentrum.de/wms_basemapde
      layers: de_basemapde_web_raster_farbe

grids:
  webmercator:
    base: GLOBAL_WEBMERCATOR

globals:
```
