"""
Unit tests for WMS metadata manager functionality.
"""
from unittest.mock import Mock, patch
from mapproxy.source.metadata import WMSMetadataManager, get_metadata_manager


class TestWMSMetadataManager:

    def setup_method(self):
        """Setup test fixtures."""
        # Reset singleton for clean testing
        WMSMetadataManager._instance = None
        self.manager = WMSMetadataManager()

    def test_singleton_pattern(self):
        """Test that WMSMetadataManager implements singleton pattern."""
        manager1 = WMSMetadataManager()
        manager2 = WMSMetadataManager()
        manager3 = get_metadata_manager()

        assert manager1 is manager2
        assert manager2 is manager3
        assert manager1 is self.manager

    @patch('mapproxy.source.metadata.HTTPClient')
    def test_fetch_capabilities_success(self, mock_http_client):
        """Test successful GetCapabilities request."""
        # Setup mock response
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        mock_response = Mock()
        mock_response.code = 200
        mock_response.read.return_value = b"""<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0">
            <Service>
                <Title>Test WMS Service</Title>
                <Abstract>Test service description</Abstract>
            </Service>
            <Capability>
                <Layer>
                    <Name>test_layer</Name>
                    <Title>Test Layer</Title>
                    <Abstract>Test layer description</Abstract>
                </Layer>
            </Capability>
        </WMS_Capabilities>"""

        mock_client_instance.open.return_value = mock_response

        # Test method
        result = self.manager._fetch_capabilities("http://example.com/wms", {})

        # Verify result
        assert result is not None
        assert b"Test WMS Service" in result

    @patch('mapproxy.source.metadata.parse_capabilities')
    @patch('mapproxy.source.metadata.HTTPClient')
    def test_get_wms_metadata_with_layer(self, mock_http_client, mock_parse):
        """Test getting WMS metadata with specific layer."""
        # Setup mock HTTP response
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        mock_response = Mock()
        mock_response.code = 200
        mock_response.read.return_value = b"""<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0">
            <Service>
                <Title>Test WMS Service</Title>
                <Abstract>Test service description</Abstract>
            </Service>
            <Capability>
                <Layer>
                    <Name>test_layer</Name>
                    <Title>Test Layer</Title>
                    <Abstract>Test layer description</Abstract>
                </Layer>
            </Capability>
        </WMS_Capabilities>"""

        mock_client_instance.open.return_value = mock_response

        # Setup mock capabilities parser
        mock_capabilities = Mock()
        mock_capabilities.metadata.return_value = {
            'title': 'Test WMS Service',
            'abstract': 'Test service description'
        }
        mock_capabilities.layers_list.return_value = [
            {
                'name': 'test_layer',
                'title': 'Test Layer',
                'abstract': 'Test layer description'
            }
        ]
        mock_parse.return_value = mock_capabilities

        # Test method
        metadata = self.manager.get_wms_metadata("http://example.com/wms", {}, "test_layer")

        # Verify metadata
        assert 'layer' in metadata
        assert metadata['layer']['title'] == 'Test Layer'
        assert metadata['layer']['abstract'] == 'Test Layer: Test layer description'

    @patch('mapproxy.source.metadata.parse_capabilities')
    def test_request_deduplication(self, mock_parse):
        """Test that concurrent requests for the same URL are deduplicated."""
        import threading
        import time

        # Track number of actual HTTP requests
        request_count = 0
        original_fetch = self.manager._fetch_capabilities

        def mock_fetch(wms_url, auth_config=None):
            nonlocal request_count
            request_count += 1
            time.sleep(0.1)  # Simulate network delay
            return b'<WMS_Capabilities version="1.3.0"></WMS_Capabilities>'

        # Setup mock parse_capabilities to avoid parsing issues
        mock_capabilities = Mock()
        mock_capabilities.metadata.return_value = {}
        mock_capabilities.layers_list.return_value = []
        mock_parse.return_value = mock_capabilities

        self.manager._fetch_capabilities = mock_fetch

        # Make concurrent requests
        results = []
        threads = []

        def make_request():
            result = self.manager.get_wms_metadata("http://example.com/wms", {}, "test_layer")
            results.append(result)

        # Start 5 concurrent threads
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify only one HTTP request was made despite 5 concurrent calls
        assert request_count == 1
        assert len(results) == 5

        # Restore original method
        self.manager._fetch_capabilities = original_fetch

    @patch('mapproxy.source.metadata.parse_capabilities')
    def test_caching_behavior(self, mock_parse):
        """Test that responses are cached and reused."""
        call_count = 0
        original_fetch = self.manager._fetch_capabilities

        def mock_fetch(wms_url, auth_config=None):
            nonlocal call_count
            call_count += 1
            return b'<WMS_Capabilities version="1.3.0"></WMS_Capabilities>'

        # Setup mock parse_capabilities to avoid parsing issues
        mock_capabilities = Mock()
        mock_capabilities.metadata.return_value = {}
        mock_capabilities.layers_list.return_value = []
        mock_parse.return_value = mock_capabilities

        self.manager._fetch_capabilities = mock_fetch

        # Make first request
        self.manager.get_wms_metadata("http://example.com/wms", {}, "test_layer")
        assert call_count == 1

        # Make second request - should use cache
        self.manager.get_wms_metadata("http://example.com/wms", {}, "test_layer")
        assert call_count == 1  # No additional call

        # Make request with different layer but same URL - should use cache
        self.manager.get_wms_metadata("http://example.com/wms", {}, "other_layer")
        assert call_count == 1  # Still no additional call

        # Restore original method
        self.manager._fetch_capabilities = original_fetch

    # These tests removed because get_service_metadata method doesn't exist in the implementation


class TestWMSMetadataManagerIntegration:
    """Integration tests that test the metadata manager with real XML responses."""

    def setup_method(self):
        """Setup test fixtures."""
        # Reset singleton for clean testing
        WMSMetadataManager._instance = None
        self.manager = WMSMetadataManager()

    @patch('mapproxy.source.metadata.parse_capabilities')
    @patch('mapproxy.source.metadata.HTTPClient')
    def test_complex_capabilities_document(self, mock_http_client, mock_parse):
        """Test with a complex capabilities document similar to real WMS services."""
        # Setup mock HTTP response
        mock_client_instance = Mock()
        mock_http_client.return_value = mock_client_instance

        mock_response = Mock()
        mock_response.code = 200
        mock_response.read.return_value = b"""<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0">
            <Service>
                <Title>Test WMS Service</Title>
                <Abstract>Comprehensive test service for metadata extraction</Abstract>
            </Service>
            <Capability>
                <Layer>
                    <Name>administrative_boundaries</Name>
                    <Title>Administrative Boundaries</Title>
                    <Abstract>Political and administrative boundary data</Abstract>
                </Layer>
            </Capability>
        </WMS_Capabilities>"""

        mock_client_instance.open.return_value = mock_response

        # Mock capabilities with the parse_capabilities return format
        mock_capabilities = Mock()

        # Mock service metadata - make sure it returns non-empty values
        mock_capabilities.metadata.return_value = {
            'title': 'Test WMS Service',
            'abstract': 'Comprehensive test service for metadata extraction',
            'contact': {
                'person': 'Jane Smith',
                'organization': 'Mapping Solutions Inc',
                'position': 'GIS Manager',
                'email': 'jane@mappingsolutions.com',
                'phone': '+1-555-123-4567',
                'address': '123 Map Street',
                'city': 'Cartography',
                'country': 'Mapland'
            },
            'fees': 'Commercial use requires license',
            'access_constraints': 'Licensed data'
        }

        # Mock layer metadata
        mock_capabilities.layers_list.return_value = [
            {
                'name': 'administrative_boundaries',
                'title': 'Administrative Boundaries',
                'abstract': 'Political and administrative boundary data',
                'legend': {'url': 'http://mapping.gov'}
            },
            {
                'name': 'countries',
                'title': 'Country Boundaries',
                'abstract': 'International country boundaries'
            },
            {
                'name': 'transportation',
                'title': 'Transportation Network',
                'abstract': 'Roads, railways, and transportation infrastructure',
                'legend': {'url': 'http://transport.gov'}
            }
        ]

        mock_parse.return_value = mock_capabilities

        # Test service metadata extraction by calling get_wms_metadata without layer
        service_metadata = self.manager.get_wms_metadata("http://example.com/wms", {})

        # The service metadata should be there when no target_layer is specified
        assert 'service' in service_metadata
        assert service_metadata['service']['title'] == 'Test WMS Service'
        assert service_metadata['service']['abstract'] == 'Comprehensive test service for metadata extraction'
        assert service_metadata['service']['fees'] == 'Commercial use requires license'
        assert service_metadata['service']['access_constraints'] == 'Licensed data'

        contact = service_metadata['service']['contact']
        assert contact['person'] == 'Jane Smith'
        assert contact['organization'] == 'Mapping Solutions Inc'
        assert contact['position'] == 'GIS Manager'
        assert contact['email'] == 'jane@mappingsolutions.com'
        assert contact['phone'] == '+1-555-123-4567'
        assert contact['address'] == '123 Map Street'
        assert contact['city'] == 'Cartography'
        assert contact['country'] == 'Mapland'

        # Test layer metadata extraction
        admin_metadata = self.manager.get_wms_metadata("http://example.com/wms", {}, "administrative_boundaries")

        assert admin_metadata['layer']['title'] == 'Administrative Boundaries'
        expected_abstract = 'Administrative Boundaries: Political and administrative boundary data'
        assert admin_metadata['layer']['abstract'] == expected_abstract
        assert admin_metadata['layer']['attribution']['title'] == 'Layer: administrative_boundaries'
        assert admin_metadata['layer']['attribution']['url'] == 'http://mapping.gov'

        # Test nested layer
        countries_metadata = self.manager.get_wms_metadata("http://example.com/wms", {}, "countries")
        assert countries_metadata['layer']['title'] == 'Country Boundaries'
        assert countries_metadata['layer']['abstract'] == 'Country Boundaries: International country boundaries'

        # Test layer with attribution
        transport_metadata = self.manager.get_wms_metadata("http://example.com/wms", {}, "transportation")
        assert transport_metadata['layer']['title'] == 'Transportation Network'
        assert transport_metadata['layer']['attribution']['title'] == 'Layer: transportation'

    def test_comma_separated_layers_metadata(self):
        """Test metadata extraction for comma-separated layers."""
        # Mock parse_capabilities
        with patch('mapproxy.source.metadata.parse_capabilities') as mock_parse:
            mock_capabilities = Mock()
            mock_capabilities.layers_list.return_value = [
                {
                    'name': 'strassennetz',
                    'title': 'Street Network',
                    'abstract': 'Complete street network data'
                },
                {
                    'name': 'strassennetz_generalisiert',
                    'title': 'Generalized Street Network',
                    'abstract': 'Simplified street network for overview display'
                },
                {
                    'name': 'other_layer',
                    'title': 'Other Layer',
                    'abstract': 'Some other layer'
                }
            ]
            mock_parse.return_value = mock_capabilities

            # Test comma-separated layer names
            layer_name = "strassennetz,strassennetz_generalisiert"
            metadata = self.manager._find_layer_metadata(mock_capabilities, layer_name)

            # Verify combined metadata
            assert metadata['title'] == 'Street Network + Generalized Street Network'
            expected_abstract = ('Street Network: Complete street network data + '
                                 'Generalized Street Network: Simplified street network for overview display')
            assert metadata['abstract'] == expected_abstract

    def test_comma_separated_layers_with_missing(self):
        """Test metadata extraction for comma-separated layers with some missing."""
        with patch('mapproxy.source.metadata.parse_capabilities') as mock_parse:
            mock_capabilities = Mock()
            mock_capabilities.layers_list.return_value = [
                {
                    'name': 'strassennetz',
                    'title': 'Street Network',
                    'abstract': 'Complete street network data'
                }
            ]
            mock_parse.return_value = mock_capabilities

            # Test with one existing and one missing layer
            with patch('mapproxy.source.metadata.log') as mock_log:
                metadata = self.manager._find_layer_metadata(mock_capabilities, "strassennetz,missing_layer")

                # Should still return metadata for found layer
                assert metadata['title'] == 'Street Network'
                assert metadata['abstract'] == 'Street Network: Complete street network data'

                # Should log warning about missing layer
                mock_log.warning.assert_called_with("Layers ['missing_layer'] not found in WMS capabilities")

    def test_comma_separated_layers_all_missing(self):
        """Test metadata extraction for comma-separated layers when all are missing."""
        with patch('mapproxy.source.metadata.parse_capabilities') as mock_parse:
            mock_capabilities = Mock()
            mock_capabilities.layers_list.return_value = [
                {
                    'name': 'other_layer',
                    'title': 'Other Layer',
                    'abstract': 'Some other layer'
                }
            ]
            mock_parse.return_value = mock_capabilities

            # Test with all missing layers
            with patch('mapproxy.source.metadata.log') as mock_log:
                metadata = self.manager._find_layer_metadata(mock_capabilities, "missing1,missing2")

                # Should return empty metadata
                assert metadata == {}

                # Should log warning about missing layers
                expected_call = "Layers ['missing1', 'missing2'] not found in WMS capabilities"
                mock_log.warning.assert_called_with(expected_call)
