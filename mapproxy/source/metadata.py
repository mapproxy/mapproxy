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

"""
Automatic metadata extraction and merging from WMS sources.
"""

import logging
from io import BytesIO
from urllib.parse import urlparse

from mapproxy.client.http import open_url, HTTPClientError, HTTPClient, auth_data_from_url
from mapproxy.request.base import BaseRequest, url_decode
from mapproxy.util.ext import wmsparse

log = logging.getLogger('mapproxy.source.metadata')


class WMSMetadataManager(object):
    """
    Manages automatic metadata extraction from WMS sources.
    """

    def __init__(self):
        self._cache = {}

    def get_source_metadata(self, url, version='1.1.1', username=None, password=None):
        """
        Fetch and parse metadata from a WMS GetCapabilities document.

        Args:
            url: WMS base URL
            version: WMS version (default: 1.1.1)
            username: Basic auth username (optional)
            password: Basic auth password (optional)

        Returns:
            dict: Parsed metadata dictionary with 'service' and 'layers' keys
        """
        cache_key = (url, version, username, password)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            capabilities_url = self._build_capabilities_url(url, version)
            log.debug('Fetching metadata from %s', capabilities_url)

            # Check if URL contains auth info or use provided credentials
            clean_url, (url_username, url_password) = auth_data_from_url(capabilities_url)
            if url_username or url_password:
                # Use auth data from URL
                http_client = HTTPClient(clean_url, url_username, url_password)
                capabilities_response = http_client.open(clean_url)
            elif username or password:
                # Use provided credentials
                http_client = HTTPClient(capabilities_url, username, password)
                capabilities_response = http_client.open(capabilities_url)
            else:
                # No authentication
                capabilities_response = open_url(capabilities_url)
            capabilities_data = BytesIO(capabilities_response.read())

            service = wmsparse.parse_capabilities(capabilities_data)
            service_metadata = service.metadata()
            layers_list = service.layers_list()

            # Clean up metadata - remove None values and normalize structure
            cleaned_service_metadata = self._clean_metadata(service_metadata)
            cleaned_layers_metadata = self._extract_layers_metadata(layers_list)

            result = {
                'service': cleaned_service_metadata,
                'layers': cleaned_layers_metadata
            }

            self._cache[cache_key] = result
            log.info('Successfully fetched metadata from %s (%d layers)', url, len(cleaned_layers_metadata))
            return result

        except HTTPClientError as ex:
            log.warning('Failed to fetch metadata from %s: %s', url, ex)
            return {'service': {}, 'layers': {}}
        except Exception as ex:
            log.warning('Error parsing metadata from %s: %s', url, ex)
            return {'service': {}, 'layers': {}}

    def _build_capabilities_url(self, url, version):
        """Build GetCapabilities URL from base WMS URL."""
        parsed_url = urlparse(url)
        base_req = BaseRequest(
            url=url.split('?', 1)[0],
            param=url_decode(parsed_url.query),
        )

        base_req.params['service'] = 'WMS'
        base_req.params['version'] = version
        base_req.params['request'] = 'GetCapabilities'
        return base_req.complete_url

    def _clean_metadata(self, metadata):
        """Clean and normalize metadata structure."""
        if not metadata:
            return {}

        cleaned = {}

        # Map important fields
        field_mapping = {
            'title': 'title',
            'abstract': 'abstract',
            'online_resource': 'online_resource',
            'fees': 'fees',
            'access_constraints': 'access_constraints',
            'contact': 'contact'
        }

        for source_key, dest_key in field_mapping.items():
            if source_key in metadata and metadata[source_key]:
                # Skip empty strings and None values
                value = metadata[source_key]
                if value and str(value).strip():
                    cleaned[dest_key] = value

        return cleaned

    def _extract_layers_metadata(self, layers_list):
        """
        Extract metadata from WMS layers list.
        
        Args:
            layers_list: List of layer dictionaries from WMS capabilities
            
        Returns:
            dict: Dictionary mapping layer names to their metadata
        """
        layers_metadata = {}
        
        for layer in layers_list:
            layer_name = layer.get('name')
            if not layer_name:
                continue
                
            # Extract relevant metadata fields
            layer_metadata = {}
            
            if layer.get('title'):
                layer_metadata['title'] = layer['title']
            if layer.get('abstract'):
                layer_metadata['abstract'] = layer['abstract']
                
            # Only store layer metadata if it has content
            if layer_metadata:
                layers_metadata[layer_name] = layer_metadata
                
        return layers_metadata

    def merge_metadata(self, service_metadata, source_metadatas):
        """
        Merge service metadata with source metadata(s).
        Priority: service_metadata > source_metadata > defaults

        Args:
            service_metadata: Configured service metadata dict
            source_metadatas: List of source metadata dicts

        Returns:
            dict: Merged metadata
        """
        merged = {}

        # Start with aggregated source metadata
        for source_md in source_metadatas:
            for key, value in source_md.items():
                if key not in merged and value:
                    merged[key] = value

        # Override with service metadata
        for key, value in service_metadata.items():
            if value:  # Only override with non-empty values
                merged[key] = value

        # Merge contact information specially
        if 'contact' in merged or any('contact' in md for md in source_metadatas):
            merged['contact'] = self._merge_contact_info(
                service_metadata.get('contact', {}),
                [md.get('contact', {}) for md in source_metadatas]
            )

        return merged

    def get_layer_metadata(self, layer_name, source_urls, layer_config=None, auth_configs=None):
        """
        Get merged metadata for a specific layer from multiple sources.
        
        Args:
            layer_name: Name of the layer to get metadata for
            source_urls: List of WMS source URLs to fetch metadata from
            layer_config: Optional layer configuration dict to merge
            auth_configs: Optional dict mapping source URLs to auth credentials
                         Format: {url: {'username': 'user', 'password': 'pass'}}
            
        Returns:
            dict: Merged layer metadata
        """
        if layer_config is None:
            layer_config = {}
        if auth_configs is None:
            auth_configs = {}
            
        source_layer_metadata = []
        
        # Collect layer metadata from all sources
        for source_url in source_urls:
            # Get auth credentials for this source URL
            auth_config = auth_configs.get(source_url, {})
            username = auth_config.get('username')
            password = auth_config.get('password')
            
            source_metadata = self.get_source_metadata(source_url, username=username, password=password)
            layers_metadata = source_metadata.get('layers', {})
            
            # Try to find matching layer metadata with fallback strategies
            layer_metadata = self._find_matching_layer_metadata(layer_name, layers_metadata)
            if layer_metadata:
                source_layer_metadata.append(layer_metadata)
                
        # Merge layer metadata
        return self.merge_layer_metadata(layer_config, source_layer_metadata)
        
    def _find_matching_layer_metadata(self, layer_name, layers_metadata):
        """
        Find matching layer metadata using various strategies.
        
        Args:
            layer_name: Layer name to search for
            layers_metadata: Dictionary of layer names to metadata
            
        Returns:
            dict: Layer metadata if found, empty dict otherwise
        """
        if not layer_name or not layers_metadata:
            return {}
            
        # Strategy 1: Exact match
        if layer_name in layers_metadata:
            return layers_metadata[layer_name]
            
        # Strategy 2: Case-insensitive match
        lower_layer_name = layer_name.lower()
        for source_layer_name, metadata in layers_metadata.items():
            if source_layer_name.lower() == lower_layer_name:
                return metadata
                
        # Strategy 3: Partial match (source layer name contains our layer name)
        for source_layer_name, metadata in layers_metadata.items():
            if layer_name in source_layer_name or source_layer_name in layer_name:
                return metadata
                
        # No match found
        return {}
        
    def merge_layer_metadata(self, layer_config, source_layer_metadata):
        """
        Merge layer configuration with source layer metadata.
        Priority: layer_config > source_layer_metadata > defaults
        
        Args:
            layer_config: Configured layer metadata dict
            source_layer_metadata: List of source layer metadata dicts
            
        Returns:
            dict: Merged layer metadata
        """
        merged = {}
        
        # Start with aggregated source metadata
        for source_md in source_layer_metadata:
            for key, value in source_md.items():
                if key not in merged and value:
                    merged[key] = value
                    
        # Override with layer configuration
        for key, value in layer_config.items():
            if value:  # Only override with non-empty values
                merged[key] = value
                
        return merged
    def _merge_contact_info(self, service_contact, source_contacts):
        """Merge contact information from multiple sources."""
        merged_contact = {}

        # Start with source contacts
        for source_contact in source_contacts:
            if source_contact:
                for key, value in source_contact.items():
                    if key not in merged_contact and value:
                        merged_contact[key] = value

        # Override with service contact info
        if service_contact:
            for key, value in service_contact.items():
                if value:
                    merged_contact[key] = value

        return merged_contact if merged_contact else None


# Global instance
metadata_manager = WMSMetadataManager()
