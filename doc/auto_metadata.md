# Automatic Metadata Inheritance

## Overview

MapProxy supports automatic metadata inheritance from source WMS services at the **layer level**. Instead of manually defining all metadata for layers, you can configure MapProxy to automatically fetch and merge metadata from the WMS sources that each layer uses.

## Layer-Level Configuration

### Basic Layer Auto Metadata

Configure individual layers to inherit metadata from their own WMS sources:

```yaml
sources:
  geoserver_wms:
    type: wms
    req:
      url: http://geoserver.example.com/wms
      layers: workspace:roads

layers:
  - name: roads
    title: "Road Network"  # Manual title
    sources: [geoserver_wms]
    md:
      abstract: "Custom road layer description"  # Manual description
      auto_metadata: true  # Inherit metadata from layer's WMS sources
```

### Auto Metadata Flag

The `auto_metadata` flag controls whether a layer inherits metadata from its own WMS sources:

- `auto_metadata: true` - Layer inherits metadata from its WMS sources
- `auto_metadata: false` or omitted - Layer uses only manual configuration

```yaml
layers:
  # Layer with auto metadata enabled
  - name: layer1
    sources: [upstream_wms1]
    md:
      auto_metadata: true  # Inherits from upstream_wms1
      
  # Layer with auto metadata disabled  
  - name: layer2
    sources: [upstream_wms2]
    md:
      abstract: "Manual description only"
      # auto_metadata: false (default)
```

### Multiple WMS Sources

Layers can inherit metadata from multiple WMS sources:

```yaml
sources:
  osm_wms:
    type: wms
    req:
      url: http://osm.example.com/wms
      layers: osm
      
  aerial_wms:
    type: wms
    req:
      url: http://aerial.example.com/wms
      layers: aerial
    wms_opts:
      version: "1.3.0"

layers:
  - name: combined_layer
    sources: [osm_wms, aerial_wms]  # Multiple sources
    md:
      auto_metadata: true  # Inherits from both WMS sources
      title: "Custom Combined Layer"  # Override title
```

### Cache Sources

Auto metadata also works with cache sources by extracting WMS URLs from underlying sources:

```yaml
sources:
  upstream_wms:
    type: wms
    req:
      url: http://example.com/wms
      layers: data_layer

caches:
  data_cache:
    sources: [upstream_wms]
    grids: [GLOBAL_MERCATOR]

layers:
  - name: cached_layer
    sources: [data_cache]  # Uses cache source
    md:
      auto_metadata: true  # Inherits from upstream_wms via cache
```

### Layer Matching Strategies

MapProxy uses the layer name to match with source WMS layers using multiple strategies:

1. **Exact match**: Layer name matches exactly
2. **Case-insensitive match**: `Roads` matches `roads`
3. **Partial match**: `roads` matches `transport:roads` or `roads_primary`

```yaml
layers:
  - name: buildings  # Will match "buildings", "Buildings", or "landuse:buildings"
    sources: [geoserver_wms]
    md:
      auto_metadata: true
```

### Layer Metadata Priority

Layer metadata is merged with the following priority (highest to lowest):

1. **Manual layer configuration** (`layers[].md`)
2. **Source WMS layer metadata** (from layer's WMS sources)
3. **Default values**

```yaml
# Source WMS layer provides:
# title: "Source Layer Title"
# abstract: "Source layer description"
# keywords: ["source", "metadata"]

layers:
  - name: my_layer
    title: "Custom Layer Title"  # Overrides source
    sources: [upstream_wms]
    md:
      # abstract inherited from source WMS layer metadata
      # keywords inherited from source WMS layer metadata
      author: "Custom Author"  # Additional manual field
      auto_metadata: true  # Enable inheritance from WMS sources
```

## Supported Metadata Fields

The following metadata fields are automatically inherited from source WMS GetCapabilities documents:

**Service-level fields** (applied to layers when available):
- `title` - Layer title
- `abstract` - Layer description  
- `fees` - Fee information
- `access_constraints` - Access constraints
- `contact` - Contact information (person, organization, email, phone, etc.)

**Layer-specific fields**:
- `title` - Layer title
- `abstract` - Layer description
- `keywords` - Layer keywords
- `metadata` - Layer metadata URLs
- `attribution` - Layer attribution information

## Error Handling

- If a source WMS is unreachable, metadata inheritance continues with available sources
- Non-WMS sources are skipped (tile sources, debug sources, etc.)
- Missing sources are logged but don't prevent layer creation
- HTTP errors during GetCapabilities requests are logged but not fatal
- Layers without WMS sources skip auto metadata silently

## Caching

Source WMS metadata is cached in memory to avoid repeated GetCapabilities requests:

- Cache key: `(url, version)`
- Cache persists for the lifetime of the MapProxy process
- No persistent caching across restarts

## Performance Considerations

- GetCapabilities requests are made during MapProxy startup/configuration reload
- Failed requests have timeouts to prevent blocking startup
- Consider network latency when configuring multiple source WMS services

## Examples

### Simple Layer with Auto Metadata

```yaml
sources:
  geoserver:
    type: wms
    req:
      url: http://geoserver.example.com/geoserver/wms
      layers: workspace:layer

layers:
  - name: proxied_layer
    sources: [geoserver]
    md:
      auto_metadata: true  # Inherits all metadata from geoserver
```

### Layer with Mixed Manual and Auto Metadata

```yaml
sources:
  external_wms:
    type: wms  
    req:
      url: http://external.provider.com/wms
      layers: data_layer

layers:
  - name: internal_layer
    title: "Internal Layer Name"  # Manual override
    sources: [external_wms]
    md:
      auto_metadata: true
      # abstract, keywords inherited from external_wms
      contact:
        organization: "My Organization"  # Manual override
        email: "contact@myorg.com"
      # Other contact fields inherited from source
```

### Multi-Source Layer

```yaml
sources:
  wms_source1:
    type: wms
    req:
      url: http://provider1.com/wms
      layers: layer1
      
  wms_source2:
    type: wms
    req:
      url: http://provider2.com/wms
      layers: layer2

layers:
  - name: combined_data
    sources: [wms_source1, wms_source2]
    md:
      auto_metadata: true  # Inherits from both sources
      title: "Combined Dataset"  # Manual title
```

## Migration from Manual Configuration

To migrate existing manual metadata configurations:

1. Add `auto_metadata: true` to layer metadata
2. Remove redundant metadata fields from `layers[].md`
3. Keep custom/override fields in `layers[].md`
4. Test that layer metadata contains expected values

## Troubleshooting

### Debug Logging

Enable debug logging to see metadata inheritance details:

```yaml
globals:
  # Enable debug logging for metadata operations
  # Check logs for "mapproxy.source.metadata" entries
```

### Common Issues

- **Empty metadata**: Check that source WMS GetCapabilities is accessible and valid
- **Missing fields**: Some WMS services may not provide complete layer metadata
- **Layer not found**: Check layer matching - try exact layer name from source WMS
- **Network timeouts**: Increase HTTP timeout if source WMS is slow to respond
- **Version conflicts**: Ensure WMS version compatibility between source and MapProxy

### Validation

Test your configuration by checking the layer metadata in GetCapabilities:

```bash
# Check if GetCapabilities includes inherited layer metadata
curl "http://localhost:8080/service?SERVICE=WMS&REQUEST=GetCapabilities"
```