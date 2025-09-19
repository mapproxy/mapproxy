"""
Integration tests for auto metadata configuration loading functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from mapproxy.config.loader import ConfigurationError, load_configuration
from mapproxy.source.metadata import WMSMetadataManager


class TestAutoMetadataConfigLoading:
    """Test auto metadata integration with configuration loading."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.base_config = {
            'services': {
                'wms': {
                    'md': {
                        'title': 'Test Service'
                    }
                }
            },
            'layers': [],
            'caches': {},
            'sources': {},
            'grids': {}
        }
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_layer_auto_metadata_enabled(self, mock_metadata_manager):
        """Test layer configuration with auto metadata enabled."""
        # Setup mock metadata manager
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        mock_manager_instance.get_layer_metadata.return_value = {
            'title': 'Remote Layer Title',
            'abstract': 'Remote Layer: Remote layer description',
            'attribution': 'Remote Attribution'
        }
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'test_layer',
                'sources': ['test_cache'],
                'md': {
                    'auto_metadata': True,
                    'title': 'Manual Override'  # Should take priority
                }
            }],
            'caches': {
                'test_cache': {
                    'sources': ['test_wms']
                }
            },
            'sources': {
                'test_wms': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'remote_layer'
                    }
                }
            }
        })
        
        loaded_config = load_configuration(config)
        
        # Verify metadata manager was called
        mock_manager_instance.get_layer_metadata.assert_called_once_with(
            'http://example.com/wms',
            'remote_layer',
            {}
        )
        
        # Verify layer metadata was merged correctly
        layer_md = loaded_config['layers'][0]['md']
        assert layer_md['title'] == 'Manual Override'  # Manual takes priority
        assert layer_md['abstract'] == 'Remote Layer: Remote layer description'  # From auto metadata
        assert layer_md['attribution'] == 'Remote Attribution'  # From auto metadata
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_layer_auto_metadata_with_authentication(self, mock_metadata_manager):
        """Test layer auto metadata with WMS authentication."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        mock_manager_instance.get_layer_metadata.return_value = {
            'title': 'Secure Layer'
        }
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'secure_layer',
                'sources': ['secure_cache'],
                'md': {
                    'auto_metadata': True
                }
            }],
            'caches': {
                'secure_cache': {
                    'sources': ['secure_wms']
                }
            },
            'sources': {
                'secure_wms': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://secure.example.com/wms',
                        'layers': 'secure_layer'
                    },
                    'http': {
                        'username': 'testuser',
                        'password': 'testpass',
                        'headers': {
                            'X-API-Key': 'secret123'
                        }
                    }
                }
            }
        })
        
        load_configuration(config)
        
        # Verify metadata manager was called with auth config
        args, kwargs = mock_manager_instance.get_layer_metadata.call_args
        auth_config = args[2]  # Third argument is auth_config
        
        assert auth_config['username'] == 'testuser'
        assert auth_config['password'] == 'testpass'
        assert auth_config['headers']['X-API-Key'] == 'secret123'
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_complex_source_specification(self, mock_metadata_manager):
        """Test auto metadata with complex source:layer specification."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        mock_manager_instance.get_layer_metadata.return_value = {
            'title': 'Complex Layer'
        }
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'complex_layer',
                'sources': ['complex_cache'],
                'md': {
                    'auto_metadata': True
                }
            }],
            'caches': {
                'complex_cache': {
                    'sources': ['complex_wms']
                }
            },
            'sources': {
                'complex_wms': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'source_lhm_plan:plan:g_fnp'
                    }
                }
            }
        })
        
        load_configuration(config)
        
        # Verify metadata manager was called with parsed layer name
        args, kwargs = mock_manager_instance.get_layer_metadata.call_args
        layer_name = args[1]  # Second argument is layer_name
        
        assert layer_name == 'g_fnp'  # Should parse complex specification
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_multi_source_layer_metadata_merging(self, mock_metadata_manager):
        """Test auto metadata merging from multiple WMS sources."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        
        # Return different metadata for different sources
        def mock_get_metadata(url, layer_name, auth_config):
            if 'source1' in url:
                return {
                    'title': 'Source 1 Title',
                    'abstract': 'Source 1: Description from source 1',
                    'attribution': 'Source 1 Attribution'
                }
            elif 'source2' in url:
                return {
                    'abstract': 'Source 2: Description from source 2',
                    'contact': {'person': 'Source 2 Contact'}
                }
            return {}
        
        mock_manager_instance.get_layer_metadata.side_effect = mock_get_metadata
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'multi_source_layer',
                'sources': ['cache1', 'cache2'],
                'md': {
                    'auto_metadata': True
                }
            }],
            'caches': {
                'cache1': {
                    'sources': ['wms1']
                },
                'cache2': {
                    'sources': ['wms2']
                }
            },
            'sources': {
                'wms1': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://source1.example.com/wms',
                        'layers': 'layer1'
                    }
                },
                'wms2': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://source2.example.com/wms',
                        'layers': 'layer2'
                    }
                }
            }
        })
        
        loaded_config = load_configuration(config)
        
        # Verify both sources were called
        assert mock_manager_instance.get_layer_metadata.call_count == 2
        
        # Verify metadata was merged (first non-empty value wins)
        layer_md = loaded_config['layers'][0]['md']
        assert layer_md['title'] == 'Source 1 Title'  # From first source
        assert layer_md['abstract'] == 'Source 1: Description from source 1'  # From first source
        assert layer_md['attribution'] == 'Source 1 Attribution'  # From first source
        assert layer_md['contact']['person'] == 'Source 2 Contact'  # From second source
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_service_auto_metadata_enabled(self, mock_metadata_manager):
        """Test service configuration with auto metadata enabled."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        
        # Mock service metadata from different WMS sources
        def mock_get_service_metadata(url, auth_config):
            if 'source1' in url:
                return {
                    'title': 'Source 1 Service',
                    'abstract': 'Service from source 1',
                    'contact': {'organization': 'Org 1'}
                }
            elif 'source2' in url:
                return {
                    'abstract': 'Service from source 2',
                    'fees': 'Commercial license required',
                    'contact': {'person': 'Contact Person'}
                }
            return {}
        
        mock_manager_instance.get_service_metadata.side_effect = mock_get_service_metadata
        
        config = self.base_config.copy()
        config.update({
            'services': {
                'wms': {
                    'md': {
                        'auto_metadata': True,
                        'title': 'Manual Service Title'  # Should take priority
                    }
                }
            },
            'layers': [
                {
                    'name': 'layer1',
                    'sources': ['cache1']
                },
                {
                    'name': 'layer2',
                    'sources': ['cache2']
                }
            ],
            'caches': {
                'cache1': {
                    'sources': ['wms1']
                },
                'cache2': {
                    'sources': ['wms2']
                }
            },
            'sources': {
                'wms1': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://source1.example.com/wms',
                        'layers': 'layer1'
                    }
                },
                'wms2': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://source2.example.com/wms',
                        'layers': 'layer2'
                    }
                }
            }
        })
        
        loaded_config = load_configuration(config)
        
        # Verify both WMS sources were called for service metadata
        assert mock_manager_instance.get_service_metadata.call_count == 2
        
        # Verify service metadata was merged correctly
        service_md = loaded_config['services']['wms']['md']
        assert service_md['title'] == 'Manual Service Title'  # Manual takes priority
        assert service_md['abstract'] == 'Service from source 1'  # From first source
        assert service_md['fees'] == 'Commercial license required'  # From second source
        assert service_md['contact']['organization'] == 'Org 1'  # From first source
        assert service_md['contact']['person'] == 'Contact Person'  # From second source
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_auto_metadata_disabled(self, mock_metadata_manager):
        """Test that auto metadata is not processed when disabled."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'manual_layer',
                'sources': ['manual_cache'],
                'md': {
                    'title': 'Manual Title',
                    'abstract': 'Manual Description'
                    # auto_metadata not set (defaults to False)
                }
            }],
            'caches': {
                'manual_cache': {
                    'sources': ['manual_wms']
                }
            },
            'sources': {
                'manual_wms': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'manual_layer'
                    }
                }
            }
        })
        
        loaded_config = load_configuration(config)
        
        # Verify metadata manager was not called
        mock_manager_instance.get_layer_metadata.assert_not_called()
        
        # Verify only manual metadata is present
        layer_md = loaded_config['layers'][0]['md']
        assert layer_md['title'] == 'Manual Title'
        assert layer_md['abstract'] == 'Manual Description'
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_auto_metadata_with_non_wms_sources(self, mock_metadata_manager):
        """Test auto metadata handling when layer has non-WMS sources."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'mixed_layer',
                'sources': ['tile_cache', 'wms_cache'],
                'md': {
                    'auto_metadata': True
                }
            }],
            'caches': {
                'tile_cache': {
                    'sources': ['tile_source']
                },
                'wms_cache': {
                    'sources': ['wms_source']
                }
            },
            'sources': {
                'tile_source': {
                    'type': 'tile',
                    'url': 'http://example.com/tiles/%(z)s/%(x)s/%(y)s.png'
                },
                'wms_source': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://example.com/wms',
                        'layers': 'wms_layer'
                    }
                }
            }
        })
        
        mock_manager_instance.get_layer_metadata.return_value = {
            'title': 'WMS Layer Title'
        }
        
        loaded_config = load_configuration(config)
        
        # Verify metadata manager was called only for WMS source
        mock_manager_instance.get_layer_metadata.assert_called_once_with(
            'http://example.com/wms',
            'wms_layer',
            {}
        )
        
        # Verify WMS metadata was applied
        layer_md = loaded_config['layers'][0]['md']
        assert layer_md['title'] == 'WMS Layer Title'
    
    @patch('mapproxy.config.loader.WMSMetadataManager')
    def test_auto_metadata_error_handling(self, mock_metadata_manager):
        """Test that auto metadata errors don't prevent configuration loading."""
        mock_manager_instance = Mock()
        mock_metadata_manager.return_value = mock_manager_instance
        
        # Simulate metadata fetching error
        mock_manager_instance.get_layer_metadata.return_value = {}  # Empty metadata
        
        config = self.base_config.copy()
        config.update({
            'layers': [{
                'name': 'error_layer',
                'sources': ['error_cache'],
                'md': {
                    'auto_metadata': True,
                    'title': 'Fallback Title'
                }
            }],
            'caches': {
                'error_cache': {
                    'sources': ['error_wms']
                }
            },
            'sources': {
                'error_wms': {
                    'type': 'wms',
                    'req': {
                        'url': 'http://unreachable.example.com/wms',
                        'layers': 'error_layer'
                    }
                }
            }
        })
        
        # Should not raise an exception
        loaded_config = load_configuration(config)
        
        # Verify fallback/manual metadata is preserved
        layer_md = loaded_config['layers'][0]['md']
        assert layer_md['title'] == 'Fallback Title'


class TestAutoMetadataHelperMethods:
    """Test helper methods for auto metadata functionality."""
    
    def test_extract_auth_config_basic_auth(self):
        """Test authentication config extraction for basic auth."""
        from mapproxy.config.loader import ProxyConfiguration
        
        source_config = {
            'type': 'wms',
            'req': {
                'url': 'http://example.com/wms',
                'layers': 'test'
            },
            'http': {
                'username': 'user',
                'password': 'pass'
            }
        }
        
        proxy_config = ProxyConfiguration(None, seed=False, renderd_address=None)
        auth_config = proxy_config._extract_auth_config(source_config)
        
        assert auth_config['username'] == 'user'
        assert auth_config['password'] == 'pass'
    
    def test_extract_auth_config_headers(self):
        """Test authentication config extraction for header auth."""
        from mapproxy.config.loader import ProxyConfiguration
        
        source_config = {
            'type': 'wms',
            'req': {
                'url': 'http://example.com/wms',
                'layers': 'test'
            },
            'http': {
                'headers': {
                    'Authorization': 'Bearer token123',
                    'X-API-Key': 'secret'
                }
            }
        }
        
        proxy_config = ProxyConfiguration(None, seed=False, renderd_address=None)
        auth_config = proxy_config._extract_auth_config(source_config)
        
        assert auth_config['headers']['Authorization'] == 'Bearer token123'
        assert auth_config['headers']['X-API-Key'] == 'secret'
    
    def test_determine_target_layer_simple(self):
        """Test target layer determination for simple layer specification."""
        from mapproxy.config.loader import ProxyConfiguration
        
        proxy_config = ProxyConfiguration(None, seed=False, renderd_address=None)
        
        # Simple layer name
        target = proxy_config._determine_target_layer('simple_layer')
        assert target == 'simple_layer'
    
    def test_determine_target_layer_complex(self):
        """Test target layer determination for complex layer specification."""
        from mapproxy.config.loader import ProxyConfiguration
        
        proxy_config = ProxyConfiguration(None, seed=False, renderd_address=None)
        
        # Complex specification
        target = proxy_config._determine_target_layer('source_lhm_plan:plan:g_fnp')
        assert target == 'g_fnp'
        
        # Another complex example
        target = proxy_config._determine_target_layer('prefix:middle:suffix:final')
        assert target == 'final'