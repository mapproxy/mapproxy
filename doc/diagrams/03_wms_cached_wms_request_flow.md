This diagram visualizes a WMS request for a cache source that also requests a WMS.


Request:

```bash
rm -rf ../../apps/base/cache_data/basemap_cache_EPSG3857/
curl -X GET --location "http://localhost:8080/service?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image%2Fpng&TRANSPARENT=true&LAYERS=basemap&CRS=EPSG%3A3857&STYLES&WIDTH=1815&HEIGHT=900&BBOX=698676.3364349005%2C6770730.613305131%2C781140.3202035681%2C6811621.844925959"
```


Configuration:

```yaml
services:
  wms:

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
