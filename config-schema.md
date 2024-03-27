not validatable with json schema
--------------------------------
* `layer.sources` should only contain values from `sources` or `caches`
* `cache.source` should only contain values from `sources`
* Cannot check if supported layers are a super set of requested layers in wms source config
  * `_validate_tagged_layer_source`, source has both `layers` and `req.layers`
* `cache.grid` is in known grids
* Cannot check if mapserver binary exists
