"""
Unit tests for WMS metadata manager functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from mapproxy.source.metadata import WMSMetadataManager, get_metadata_manager
from mapproxy.client.http import HTTPClientError


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
    
    @patch('mapproxy.source.metadata.HTTPClient')
    def test_get_wms_metadata_with_layer(self, mock_http_client):
        """Test getting WMS metadata with specific layer."""
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
        metadata = self.manager.get_wms_metadata("http://example.com/wms", {}, "test_layer")
        
        # Verify metadata
        assert 'layer' in metadata
        assert metadata['layer']['title'] == 'Test Layer'
        assert metadata['layer']['abstract'] == 'Test Layer: Test layer description'
    
    def test_request_deduplication(self):
        """Test that concurrent requests for the same URL are deduplicated."""
        import threading
        import time
        
        # Track number of actual HTTP requests
        request_count = 0
        original_fetch = self.manager._fetch_capabilities
        
        def mock_fetch(url, auth_config):
            nonlocal request_count
            request_count += 1
            time.sleep(0.1)  # Simulate network delay
            return b'<WMS_Capabilities version="1.3.0"></WMS_Capabilities>'
        
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
    
    def test_caching_behavior(self):
        """Test that responses are cached and reused."""
        call_count = 0
        original_fetch = self.manager._fetch_capabilities
        
        def mock_fetch(url, auth_config):
            nonlocal call_count
            call_count += 1
            return b'<WMS_Capabilities version="1.3.0"></WMS_Capabilities>'
        
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
    
    @patch.object(WMSMetadataManager, '_fetch_capabilities')
    def test_get_service_metadata_success(self, mock_fetch):
        """Test successful service metadata retrieval."""
        capabilities_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0">
            <Service>
                <Title>Test Service</Title>
                <Abstract>Test service description</Abstract>
            </Service>
        </WMS_Capabilities>"""
        
        from xml.etree import ElementTree as ET
        mock_fetch.return_value = ET.fromstring(capabilities_xml)
        
        metadata = self.manager.get_service_metadata("http://example.com/wms", {})
        
        assert metadata['title'] == 'Test Service'
        assert metadata['abstract'] == 'Test service description'
    
    @patch.object(WMSMetadataManager, '_fetch_capabilities')
    def test_get_service_metadata_capabilities_error(self, mock_fetch):
        """Test service metadata retrieval when GetCapabilities fails."""
        mock_fetch.return_value = None
        
        metadata = self.manager.get_service_metadata("http://example.com/wms", {})
        
        assert metadata == {}


class TestWMSMetadataManagerIntegration:
    """Integration tests that test the metadata manager with real XML responses."""
    
    def setup_method(self):
        self.manager = WMSMetadataManager()
    
    def test_complex_capabilities_document(self):
        """Test with a complex capabilities document similar to real WMS services."""
        capabilities_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0" xmlns="http://www.opengis.net/wms">
            <Service>
                <Name>WMS</Name>
                <Title>Test WMS Service</Title>
                <Abstract>Comprehensive test service for metadata extraction</Abstract>
                <KeywordList>
                    <Keyword>mapping</Keyword>
                    <Keyword>GIS</Keyword>
                </KeywordList>
                <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="http://example.com"/>
                <ContactInformation>
                    <ContactPersonPrimary>
                        <ContactPerson>Jane Smith</ContactPerson>
                        <ContactOrganization>Mapping Solutions Inc</ContactOrganization>
                    </ContactPersonPrimary>
                    <ContactPosition>GIS Manager</ContactPosition>
                    <ContactAddress>
                        <AddressType>postal</AddressType>
                        <Address>123 Map Street</Address>
                        <City>Cartography</City>
                        <StateOrProvince>GIS</StateOrProvince>
                        <PostCode>12345</PostCode>
                        <Country>Mapland</Country>
                    </ContactAddress>
                    <ContactVoiceTelephone>+1-555-123-4567</ContactVoiceTelephone>
                    <ContactElectronicMailAddress>jane@mappingsolutions.com</ContactElectronicMailAddress>
                </ContactInformation>
                <Fees>Commercial use requires license</Fees>
                <AccessConstraints>Licensed data</AccessConstraints>
            </Service>
            <Capability>
                <Request>
                    <GetCapabilities>
                        <Format>text/xml</Format>
                    </GetCapabilities>
                    <GetMap>
                        <Format>image/png</Format>
                        <Format>image/jpeg</Format>
                    </GetMap>
                </Request>
                <Layer>
                    <Title>Root Layer</Title>
                    <CRS>EPSG:4326</CRS>
                    <CRS>EPSG:3857</CRS>
                    <Layer queryable="1">
                        <Name>administrative_boundaries</Name>
                        <Title>Administrative Boundaries</Title>
                        <Abstract>Political and administrative boundary data</Abstract>
                        <KeywordList>
                            <Keyword>boundaries</Keyword>
                            <Keyword>administrative</Keyword>
                        </KeywordList>
                        <Attribution>
                            <Title>National Mapping Agency</Title>
                            <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="http://mapping.gov"/>
                        </Attribution>
                        <Layer>
                            <Name>countries</Name>
                            <Title>Country Boundaries</Title>
                            <Abstract>International country boundaries</Abstract>
                        </Layer>
                        <Layer>
                            <Name>states</Name>
                            <Title>State Boundaries</Title>
                            <Abstract>State and province boundaries</Abstract>
                        </Layer>
                    </Layer>
                    <Layer queryable="1">
                        <Name>transportation</Name>
                        <Title>Transportation Network</Title>
                        <Abstract>Roads, railways, and transportation infrastructure</Abstract>
                        <Attribution>
                            <Title>Department of Transportation</Title>
                        </Attribution>
                    </Layer>
                </Layer>
            </Capability>
        </WMS_Capabilities>"""
        
        from xml.etree import ElementTree as ET
        capabilities = ET.fromstring(capabilities_xml)
        
        # Test service metadata extraction
        service_metadata = self.manager._extract_service_metadata(capabilities)
        
        assert service_metadata['title'] == 'Test WMS Service'
        assert service_metadata['abstract'] == 'Comprehensive test service for metadata extraction'
        assert service_metadata['fees'] == 'Commercial use requires license'
        assert service_metadata['access_constraints'] == 'Licensed data'
        
        contact = service_metadata['contact']
        assert contact['person'] == 'Jane Smith'
        assert contact['organization'] == 'Mapping Solutions Inc'
        assert contact['position'] == 'GIS Manager'
        assert contact['email'] == 'jane@mappingsolutions.com'
        assert contact['phone'] == '+1-555-123-4567'
        assert contact['address'] == '123 Map Street'
        assert contact['city'] == 'Cartography'
        assert contact['country'] == 'Mapland'
        
        # Test layer metadata extraction
        admin_metadata = self.manager._extract_layer_metadata(capabilities, "administrative_boundaries")
        
        assert admin_metadata['title'] == 'Administrative Boundaries'
        assert admin_metadata['abstract'] == 'Administrative Boundaries: Political and administrative boundary data'
        assert admin_metadata['attribution'] == 'National Mapping Agency'
        
        # Test nested layer
        countries_metadata = self.manager._extract_layer_metadata(capabilities, "countries")
        assert countries_metadata['title'] == 'Country Boundaries'
        assert countries_metadata['abstract'] == 'Country Boundaries: International country boundaries'
        
        # Test layer without attribution
        transport_metadata = self.manager._extract_layer_metadata(capabilities, "transportation")
        assert transport_metadata['title'] == 'Transportation Network'
        assert transport_metadata['attribution'] == 'Department of Transportation'
    
    def test_comma_separated_layers_metadata(self):
        """Test metadata extraction for comma-separated layers."""
        # Mock capabilities response with multiple layers
        capabilities_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities version="1.3.0">
            <Service>
                <Title>Test Multi-Layer Service</Title>
                <Abstract>Service with multiple layers</Abstract>
            </Service>
            <Capability>
                <Layer>
                    <Layer>
                        <Name>strassennetz</Name>
                        <Title>Street Network</Title>
                        <Abstract>Complete street network data</Abstract>
                    </Layer>
                    <Layer>
                        <Name>strassennetz_generalisiert</Name>
                        <Title>Generalized Street Network</Title>
                        <Abstract>Simplified street network for overview display</Abstract>
                    </Layer>
                    <Layer>
                        <Name>other_layer</Name>
                        <Title>Other Layer</Title>
                        <Abstract>Some other layer</Abstract>
                    </Layer>
                </Layer>
            </Capability>
        </WMS_Capabilities>"""
        
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
            metadata = self.manager._find_layer_metadata(mock_capabilities, "strassennetz,strassennetz_generalisiert")
            
            # Verify combined metadata
            assert metadata['title'] == 'Street Network + Generalized Street Network'
            assert metadata['abstract'] == 'Street Network: Complete street network data + Generalized Street Network: Simplified street network for overview display'
    
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
                mock_log.warning.assert_called_with("Layers ['missing1', 'missing2'] not found in WMS capabilities")