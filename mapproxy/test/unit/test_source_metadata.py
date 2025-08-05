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
from io import BytesIO
from unittest.mock import Mock, patch

from mapproxy.source.metadata import WMSMetadataManager, metadata_manager


class TestWMSMetadataManager:
    
    def setup_method(self):
        self.manager = WMSMetadataManager()
        # Clear cache
        self.manager._cache.clear()
    
    def test_clean_metadata(self):
        """Test metadata cleaning functionality."""
        raw_metadata = {
            'title': 'Test WMS Service',
            'abstract': 'A test service for metadata extraction',
            'online_resource': 'http://example.com/wms',
            'fees': 'None',
            'access_constraints': '',  # Empty string should be filtered
            'contact': {
                'person': 'Test Person',
                'email': 'test@example.com',
                'organization': None  # None values should be filtered
            },
            'empty_field': None,  # Should be filtered
            'whitespace_field': '   '  # Should be filtered
        }
        
        cleaned = self.manager._clean_metadata(raw_metadata)
        
        expected = {
            'title': 'Test WMS Service',
            'abstract': 'A test service for metadata extraction',
            'online_resource': 'http://example.com/wms',
            'fees': 'None',
            'contact': {
                'person': 'Test Person',
                'email': 'test@example.com',
                'organization': None
            }
        }
        
        assert cleaned == expected
    
    def test_merge_metadata_priority(self):
        """Test that service metadata has priority over source metadata."""
        service_md = {
            'title': 'Custom Service Title',
            'abstract': 'Custom abstract'
        }
        
        source_mds = [{
            'title': 'Source Title',  # Should be overridden
            'abstract': 'Source abstract',  # Should be overridden
            'fees': 'None',  # Should be kept
            'contact': {'email': 'source@example.com'}
        }]
        
        merged = self.manager.merge_metadata(service_md, source_mds)
        
        assert merged['title'] == 'Custom Service Title'
        assert merged['abstract'] == 'Custom abstract'
        assert merged['fees'] == 'None'
        assert merged['contact']['email'] == 'source@example.com'
    
    def test_merge_contact_info(self):
        """Test contact information merging."""
        service_contact = {
            'person': 'Service Contact',
            'email': 'service@example.com'
        }
        
        source_contacts = [{
            'person': 'Source Contact',  # Should be overridden
            'organization': 'Source Org',  # Should be kept
            'phone': '+1234567890'  # Should be kept
        }]
        
        merged_contact = self.manager._merge_contact_info(service_contact, source_contacts)
        
        assert merged_contact['person'] == 'Service Contact'
        assert merged_contact['email'] == 'service@example.com'
        assert merged_contact['organization'] == 'Source Org'
        assert merged_contact['phone'] == '+1234567890'
    
    def test_build_capabilities_url(self):
        """Test GetCapabilities URL building."""
        base_url = 'http://example.com/wms?map=test'
        capabilities_url = self.manager._build_capabilities_url(base_url, '1.3.0')
        
        assert 'service=WMS' in capabilities_url
        assert 'version=1.3.0' in capabilities_url
        assert 'request=GetCapabilities' in capabilities_url
        assert 'map=test' in capabilities_url
    
    @patch('mapproxy.source.metadata.open_url')
    @patch('mapproxy.source.metadata.wmsparse.parse_capabilities')
    def test_get_source_metadata_success(self, mock_parse, mock_open):
        """Test successful metadata retrieval."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.read.return_value = b'<xml>capabilities</xml>'
        mock_open.return_value = mock_response
        
        # Mock capabilities parsing
        mock_capabilities = Mock()
        mock_capabilities.metadata.return_value = {
            'title': 'Source WMS',
            'abstract': 'Test source',
            'contact': {'email': 'test@example.com'}
        }
        mock_parse.return_value = mock_capabilities
        
        metadata = self.manager.get_source_metadata('http://example.com/wms')
        
        assert metadata['title'] == 'Source WMS'
        assert metadata['abstract'] == 'Test source'
        assert metadata['contact']['email'] == 'test@example.com'
        
        # Test caching
        metadata2 = self.manager.get_source_metadata('http://example.com/wms')
        assert metadata == metadata2
        # Should only call once due to caching
        assert mock_open.call_count == 1
    
    @patch('mapproxy.source.metadata.open_url')
    def test_get_source_metadata_http_error(self, mock_open):
        """Test handling of HTTP errors."""
        from mapproxy.client.http import HTTPClientError
        mock_open.side_effect = HTTPClientError('Service unavailable')
        
        metadata = self.manager.get_source_metadata('http://example.com/wms')
        
        assert metadata == {}
    
    def test_global_metadata_manager(self):
        """Test that global metadata manager instance works."""
        assert metadata_manager is not None
        assert isinstance(metadata_manager, WMSMetadataManager)


class TestMetadataManagerIntegration:
    """Integration tests with actual XML parsing."""
    
    def test_real_capabilities_parsing(self):
        """Test with a real capabilities document structure."""
        capabilities_xml = b'''<?xml version="1.0" encoding="UTF-8"?>
<WMT_MS_Capabilities version="1.1.1">
  <Service>
    <Name>OGC:WMS</Name>
    <Title>Test WMS Service</Title>
    <Abstract>A test WMS service for metadata extraction</Abstract>
    <OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="http://example.com/wms"/>
    <ContactInformation>
      <ContactPersonPrimary>
        <ContactPerson>John Doe</ContactPerson>
        <ContactOrganization>Test Organization</ContactOrganization>
      </ContactPersonPrimary>
      <ContactPosition>Technical Lead</ContactPosition>
      <ContactAddress>
        <AddressType>postal</AddressType>
        <Address>123 Test Street</Address>
        <City>Test City</City>
        <StateOrProvince>Test State</StateOrProvince>
        <PostCode>12345</PostCode>
        <Country>Test Country</Country>
      </ContactAddress>
      <ContactVoiceTelephone>+1-555-0123</ContactVoiceTelephone>
      <ContactElectronicMailAddress>john@example.com</ContactElectronicMailAddress>
    </ContactInformation>
    <Fees>None</Fees>
    <AccessConstraints>None</AccessConstraints>
  </Service>
  <Capability>
    <Request>
      <GetMap>
        <Format>image/png</Format>
        <DCPType>
          <HTTP>
            <Get><OnlineResource xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="http://example.com/wms?"/></Get>
          </HTTP>
        </DCPType>
      </GetMap>
    </Request>
    <Layer>
      <Title>Root Layer</Title>
      <SRS>EPSG:4326</SRS>
    </Layer>
  </Capability>
</WMT_MS_Capabilities>'''
        
        with patch('mapproxy.source.metadata.open_url') as mock_open:
            mock_response = Mock()
            mock_response.read.return_value = capabilities_xml
            mock_open.return_value = mock_response
            
            manager = WMSMetadataManager()
            metadata = manager.get_source_metadata('http://example.com/wms')
            
            assert metadata['title'] == 'Test WMS Service'
            assert metadata['abstract'] == 'A test WMS service for metadata extraction'
            assert metadata['online_resource'] == 'http://example.com/wms'
            assert metadata['fees'] == 'None'
            assert metadata['access_constraints'] == 'None'
            
            contact = metadata['contact']
            assert contact['person'] == 'John Doe'
            assert contact['organization'] == 'Test Organization'
            assert contact['position'] == 'Technical Lead'
            assert contact['email'] == 'john@example.com'
            assert contact['phone'] == '+1-555-0123'


class TestLayerMetadata:
    """Tests for layer-level metadata functionality."""
    
    def setup_method(self):
        self.manager = WMSMetadataManager()
        self.manager._cache.clear()
    
    def test_extract_layers_metadata(self):
        """Test layer metadata extraction from capabilities."""
        layers_list = [
            {'name': 'layer1', 'title': 'Layer 1 Title', 'abstract': 'Layer 1 description'},
            {'name': 'layer2', 'title': 'Layer 2 Title', 'abstract': None},
            {'name': None, 'title': 'Unnamed Layer'},  # Should be skipped
            {'name': 'layer3', 'title': '', 'abstract': ''}  # Should be skipped
        ]
        
        layers_metadata = self.manager._extract_layers_metadata(layers_list)
        
        assert 'layer1' in layers_metadata
        assert layers_metadata['layer1']['title'] == 'Layer 1 Title'
        assert layers_metadata['layer1']['abstract'] == 'Layer 1 description'
        
        assert 'layer2' in layers_metadata
        assert layers_metadata['layer2']['title'] == 'Layer 2 Title'
        assert 'abstract' not in layers_metadata['layer2']
        
        assert len(layers_metadata) == 2  # Only layer1 and layer2 should be included
    
    def test_find_matching_layer_metadata(self):
        """Test layer matching strategies."""
        layers_metadata = {
            'roads': {'title': 'Roads Layer', 'abstract': 'Road network'},
            'BUILDINGS': {'title': 'Buildings Layer', 'abstract': 'Building footprints'},
            'landuse.parcels': {'title': 'Land Parcels', 'abstract': 'Land use parcels'}
        }
        
        # Test exact match
        result = self.manager._find_matching_layer_metadata('roads', layers_metadata)
        assert result['title'] == 'Roads Layer'
        
        # Test case-insensitive match
        result = self.manager._find_matching_layer_metadata('buildings', layers_metadata)
        assert result['title'] == 'Buildings Layer'
        
        # Test partial match
        result = self.manager._find_matching_layer_metadata('parcels', layers_metadata)
        assert result['title'] == 'Land Parcels'
        
        # Test no match
        result = self.manager._find_matching_layer_metadata('nonexistent', layers_metadata)
        assert result == {}
    
    def test_merge_layer_metadata(self):
        """Test layer metadata merging with priority."""
        layer_config = {
            'title': 'Custom Layer Title',
            'abstract': 'Custom layer description'
        }
        
        source_layer_metadata = [
            {
                'title': 'Source Title',  # Should be overridden
                'abstract': 'Source description',  # Should be overridden
                'keywords': ['source', 'layer']  # Should be kept
            }
        ]
        
        merged = self.manager.merge_layer_metadata(layer_config, source_layer_metadata)
        
        assert merged['title'] == 'Custom Layer Title'
        assert merged['abstract'] == 'Custom layer description'
        assert merged['keywords'] == ['source', 'layer']
    
    @patch('mapproxy.source.metadata.WMSMetadataManager.get_source_metadata')
    def test_get_layer_metadata(self, mock_get_source):
        """Test complete layer metadata retrieval and merging."""
        # Mock source metadata
        mock_get_source.return_value = {
            'service': {'title': 'Source Service'},
            'layers': {
                'test_layer': {
                    'title': 'Source Layer Title',
                    'abstract': 'Source layer description'
                }
            }
        }
        
        layer_config = {'title': 'Custom Layer Title'}
        
        result = self.manager.get_layer_metadata(
            'test_layer', 
            ['http://example.com/wms'], 
            layer_config
        )
        
        assert result['title'] == 'Custom Layer Title'  # Config has priority
        assert result['abstract'] == 'Source layer description'  # From source
        
        mock_get_source.assert_called_once_with('http://example.com/wms')
    
    @patch('mapproxy.source.metadata.open_url')
    @patch('mapproxy.source.metadata.wmsparse.parse_capabilities')
    def test_layer_metadata_with_real_structure(self, mock_parse, mock_open):
        """Test layer metadata with realistic WMS structure."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.read.return_value = b'<xml>capabilities</xml>'
        mock_open.return_value = mock_response
        
        # Mock service with layers
        mock_service = Mock()
        mock_service.metadata.return_value = {
            'title': 'Test WMS Service',
            'abstract': 'A test service'
        }
        mock_service.layers_list.return_value = [
            {
                'name': 'roads',
                'title': 'Road Network',
                'abstract': 'Complete road network data'
            },
            {
                'name': 'buildings',
                'title': 'Building Footprints',
                'abstract': 'Building outline data'
            }
        ]
        mock_parse.return_value = mock_service
        
        metadata = self.manager.get_source_metadata('http://example.com/wms')
        
        # Verify service metadata
        assert metadata['service']['title'] == 'Test WMS Service'
        
        # Verify layer metadata
        assert 'layers' in metadata
        assert 'roads' in metadata['layers']
        assert metadata['layers']['roads']['title'] == 'Road Network'
        assert metadata['layers']['roads']['abstract'] == 'Complete road network data'
        
        assert 'buildings' in metadata['layers']
        assert metadata['layers']['buildings']['title'] == 'Building Footprints'