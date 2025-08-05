# This file is part of the MapProxy project.
# Copyright (C) 2025 Omniscale <http://omniscale.de>
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

import pytest
from unittest.mock import Mock, patch

from mapproxy.config.loader import ConfigurationContext, ServiceConfiguration
from mapproxy.test.helper import TempFile


class TestLayerAutoMetadataConfiguration:
    """Test layer-level auto metadata configuration."""
    
    def test_layer_auto_metadata_with_direct_wms_source(self):
        """Test layer configuration with auto metadata using direct WMS source."""
        config = {
            'sources': {
                'wms_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'source_layer'
                    }
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'test_layer',
                    'title': 'Test Layer',
                    'sources': ['wms_source'],
                    'md': {
                        'abstract': 'Custom layer description',
                        'auto_metadata': True
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            # Mock layer metadata retrieval
            mock_manager.get_layer_metadata.return_value = {
                'title': 'Source Layer Title',
                'abstract': 'Source layer description',
                'keywords': ['source', 'layer']
            }
            
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            # Get the layer configuration
            layer_config = context.layers['test_layer']
            
            # Verify that layer metadata merge was called with layer's own source URLs
            mock_manager.get_layer_metadata.assert_called_once_with(
                'test_layer',  # Layer name used for matching
                ['http://example.com/wms'],  # URL from layer's own WMS source
                {
                    'abstract': 'Custom layer description',
                    'auto_metadata': True
                }
            )
            
            # Create WMS layer to verify metadata is properly passed
            wms_layer = layer_config.wms_layer()
            assert wms_layer is not None
            assert wms_layer.name == 'test_layer'
            assert wms_layer.title == 'Test Layer'
    
    def test_layer_auto_metadata_with_cache_source(self):
        """Test layer auto metadata when using cache sources."""
        config = {
            'sources': {
                'wms_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'layer1'
                    }
                }
            },
            'caches': {
                'test_cache': {
                    'sources': ['wms_source'],
                    'grids': ['GLOBAL_MERCATOR']
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'cached_layer',
                    'title': 'Cached Layer',
                    'sources': ['test_cache'],
                    'md': {
                        'auto_metadata': True
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            mock_manager.get_layer_metadata.return_value = {
                'title': 'Cache Source Layer',
                'keywords': ['cached']
            }
            
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            layer_config = context.layers['cached_layer']
            wms_layer = layer_config.wms_layer()
            
            # Should call with URLs from underlying WMS sources of the cache
            mock_manager.get_layer_metadata.assert_called_once_with(
                'cached_layer',
                ['http://example.com/wms'],  # URL from cache's WMS source
                {'auto_metadata': True}
            )
    
    def test_layer_auto_metadata_disabled(self):
        """Test layer auto metadata when flag is False."""
        config = {
            'sources': {
                'wms_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'layer1'
                    }
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'my_layer',
                    'title': 'My Layer',
                    'sources': ['wms_source'],
                    'md': {
                        'abstract': 'Manual description',
                        'auto_metadata': False  # Explicitly disabled
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            layer_config = context.layers['my_layer']
            wms_layer = layer_config.wms_layer()
            
            # Should not call layer metadata manager when disabled
            mock_manager.get_layer_metadata.assert_not_called()
            
            # Verify layer metadata contains only manual values
            assert wms_layer.md.get('abstract') == 'Manual description'
            assert 'auto_metadata' not in wms_layer.md  # Flag should be removed
    
    def test_layer_auto_metadata_no_wms_sources(self):
        """Test layer auto metadata when layer has no WMS sources."""
        config = {
            'sources': {
                'tile_source': {
                    'type': 'tile',
                    'url': 'http://example.com/tiles/{z}/{x}/{y}.png'
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'tile_layer',
                    'title': 'Tile Layer',
                    'sources': ['tile_source'],
                    'md': {
                        'auto_metadata': True  # Enabled but no WMS sources
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            layer_config = context.layers['tile_layer']
            wms_layer = layer_config.wms_layer()
            
            # Should not call layer metadata manager when no WMS sources found
            mock_manager.get_layer_metadata.assert_not_called()
    
    def test_layer_without_auto_metadata_flag(self):
        """Test layer configuration without auto metadata flag (default behavior)."""
        config = {
            'sources': {
                'wms_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'layer1'
                    }
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'test_layer',
                    'title': 'Test Layer',
                    'sources': ['wms_source'],
                    'md': {
                        'abstract': 'Manual layer description'
                        # No auto_metadata flag - defaults to False
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            layer_config = context.layers['test_layer']
            wms_layer = layer_config.wms_layer()
            
            # Should not call layer metadata manager when flag not present
            mock_manager.get_layer_metadata.assert_not_called()
            
            # Verify layer metadata contains manual values
            assert wms_layer.md.get('abstract') == 'Manual layer description'
    
    def test_layer_auto_metadata_multiple_wms_sources(self):
        """Test layer auto metadata with multiple WMS sources."""
        config = {
            'sources': {
                'wms_source1': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example1.com/wms',
                        'layers': 'layer1'
                    }
                },
                'wms_source2': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example2.com/wms',
                        'layers': 'layer2'
                    }
                }
            },
            'services': {
                'wms': {
                    'md': {'title': 'Test Service'}
                }
            },
            'layers': [
                {
                    'name': 'multi_layer',
                    'title': 'Multi Source Layer',
                    'sources': ['wms_source1', 'wms_source2'],
                    'md': {
                        'auto_metadata': True
                    }
                }
            ]
        }
        
        with patch('mapproxy.source.metadata.metadata_manager') as mock_manager:
            mock_manager.get_layer_metadata.return_value = {'title': 'Multi Layer'}
            
            from mapproxy.config.loader import load_configuration_context
            context = load_configuration_context(config)
            
            layer_config = context.layers['multi_layer']
            wms_layer = layer_config.wms_layer()
            
            # Should call with URLs from all WMS sources
            mock_manager.get_layer_metadata.assert_called_once_with(
                'multi_layer',
                ['http://example1.com/wms', 'http://example2.com/wms'],
                {'auto_metadata': True}
            )
    
    def test_yaml_layer_auto_metadata_configuration(self):
        """Test YAML configuration for layer auto metadata."""
        yaml_config = """
sources:
  geoserver_wms:
    type: wms
    req:
      url: http://geoserver.example.com/wms
      layers: data:roads

services:
  wms:
    md:
      title: My WMS Service

layers:
  - name: roads
    title: Road Network
    sources: [geoserver_wms]
    md:
      abstract: Custom road layer description
      auto_metadata: true
"""
        
        with TempFile() as tmp:
            tmp.write(yaml_config.encode('utf-8'))
            tmp.close()
            
            with patch('mapproxy.source.metadata.metadata_manager'):
                from mapproxy.config.config import load_configuration
                config = load_configuration(tmp.name)
                
                # Verify layer auto metadata configuration is parsed as boolean
                layer_conf = config['layers'][0]
                assert layer_conf['name'] == 'roads'
                assert layer_conf['md']['auto_metadata'] is True
                
                # Verify service no longer has auto_metadata_sources
                service_conf = config['services']['wms']
                assert 'auto_metadata_sources' not in service_conf