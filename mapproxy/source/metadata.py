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
Automatic metadata extraction from WMS sources.
"""

import logging
import time
from io import BytesIO
from urllib.parse import urlparse, parse_qs
from threading import Lock

from mapproxy.util.ext.wmsparse import parse_capabilities
from mapproxy.client.http import HTTPClient

log = logging.getLogger(__name__)


class WMSMetadataManager:
    """Manager for fetching and processing WMS metadata from GetCapabilities."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return

        self._cache = {}  # URL -> (timestamp, capabilities)
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._request_locks = {}  # URL -> Lock for deduplication
        self._requests_lock = Lock()  # Protect _request_locks dict
        self._initialized = True

    def get_wms_metadata(self, wms_url, auth_config=None, target_layer=None):
        """
        Fetch WMS metadata from GetCapabilities document with request deduplication.

        Args:
            wms_url: WMS service URL
            auth_config: Authentication configuration (username, password, headers)
            target_layer: Specific layer name to extract metadata for

        Returns:
            dict: Metadata dictionary with service and/or layer metadata
        """
        # Use URL as primary cache key for deduplication
        cache_key = wms_url

        # Check cache first
        if cache_key in self._cache:
            cached_time, capabilities = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                log.debug(f"Using cached capabilities for {wms_url}")
                return self._extract_metadata(capabilities, target_layer)

        # Get or create request lock for this URL to prevent duplicate requests
        with self._requests_lock:
            if wms_url not in self._request_locks:
                self._request_locks[wms_url] = Lock()
            request_lock = self._request_locks[wms_url]

        # Use the request lock to deduplicate concurrent requests
        with request_lock:
            # Check cache again in case another thread fetched it
            if cache_key in self._cache:
                cached_time, capabilities = self._cache[cache_key]
                if time.time() - cached_time < self._cache_ttl:
                    log.debug(f"Using freshly cached capabilities for {wms_url}")
                    return self._extract_metadata(capabilities, target_layer)

            try:
                # Fetch GetCapabilities document
                cap_doc = self._fetch_capabilities(wms_url, auth_config)

                # Parse capabilities
                capabilities = parse_capabilities(BytesIO(cap_doc))

                # Cache the capabilities (not the extracted metadata)
                self._cache[cache_key] = (time.time(), capabilities)

                # Extract and return metadata
                return self._extract_metadata(capabilities, target_layer)

            except Exception as e:
                # Log detailed error information but don't block MapProxy operation
                error_type = type(e).__name__
                log.warning(f"Failed to fetch metadata from {wms_url} ({error_type}): {e}")
                log.debug(f"Auto metadata fetch failed for {wms_url}, continuing without metadata", exc_info=True)
                return {}

    def _fetch_capabilities(self, wms_url, auth_config=None):
        """Fetch GetCapabilities document from WMS URL."""

        # Build GetCapabilities URL
        parsed_url = urlparse(wms_url)
        query_params = parse_qs(parsed_url.query)

        # Add GetCapabilities parameters - no default version
        query_params.update({
            'SERVICE': ['WMS'],
            'REQUEST': ['GetCapabilities']
        })

        # Reconstruct URL with GetCapabilities parameters
        from urllib.parse import urlencode, urlunparse
        new_query = urlencode(query_params, doseq=True)
        cap_url = urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, parsed_url.fragment
        ))

        # Setup HTTP client with authentication
        headers = {}
        username = None
        password = None

        if auth_config:
            username = auth_config.get('username')
            password = auth_config.get('password')
            headers.update(auth_config.get('headers', {}))

        # Create HTTP client with auth configuration and timeout
        # Use a shorter timeout for metadata requests to prevent blocking
        metadata_timeout = 30  # 30 seconds timeout for metadata requests
        http_client = HTTPClient(
            url=cap_url,
            username=username,
            password=password,
            headers=headers,
            timeout=metadata_timeout
        )

        # Fetch the document
        log.debug(f"Fetching GetCapabilities from {cap_url} (timeout: {metadata_timeout}s)")
        response = http_client.open(cap_url)

        if response.code != 200:
            raise Exception(f"HTTP {response.code}: {response.read()}")

        return response.read()

    def _extract_metadata(self, capabilities, target_layer=None):
        """Extract metadata from parsed capabilities."""
        metadata = {}

        # Extract service-level metadata
        service_md = capabilities.metadata()
        if service_md:
            metadata['service'] = {
                'title': service_md.get('title'),
                'abstract': service_md.get('abstract'),
                'contact': service_md.get('contact'),
                'fees': service_md.get('fees'),
                'access_constraints': service_md.get('access_constraints'),
            }

        # Extract layer-specific metadata if target_layer specified
        if target_layer:
            layer_md = self._find_layer_metadata(capabilities, target_layer)
            if layer_md:
                metadata['layer'] = layer_md

        return metadata

    def _find_layer_metadata(self, capabilities, layer_name):
        """Find and extract metadata for a specific layer or comma-separated layers."""
        layers = capabilities.layers_list()

        # Check if layer_name contains comma-separated layers
        if ',' in layer_name:
            layer_names = [name.strip() for name in layer_name.split(',')]
            return self._find_multiple_layers_metadata(capabilities, layer_names)

        # Single layer processing
        return self._find_single_layer_metadata(layers, layer_name)

    def _find_single_layer_metadata(self, layers, layer_name):
        """Find metadata for a single layer using multiple matching strategies."""
        # Try exact match first
        for layer in layers:
            if layer.get('name') == layer_name:
                return self._process_layer_metadata(layer)

        # Try case-insensitive match
        layer_name_lower = layer_name.lower()
        for layer in layers:
            if layer.get('name', '').lower() == layer_name_lower:
                return self._process_layer_metadata(layer)

        # Try partial match (contains)
        for layer in layers:
            if layer_name_lower in layer.get('name', '').lower():
                return self._process_layer_metadata(layer)

        log.warning(f"Layer '{layer_name}' not found in WMS capabilities")
        return {}

    def _find_multiple_layers_metadata(self, capabilities, layer_names):
        """Find and combine metadata for multiple layers."""
        layers = capabilities.layers_list()
        found_layers = []
        missing_layers = []

        # Find each layer using the same matching strategies
        for layer_name in layer_names:
            found_layer = self._find_layer_by_name(layers, layer_name)

            if found_layer:
                found_layers.append(found_layer)
            else:
                missing_layers.append(layer_name)

        if missing_layers:
            log.warning(f"Layers {missing_layers} not found in WMS capabilities")

        if not found_layers:
            return {}

        # Combine metadata from all found layers
        return self._combine_layers_metadata(found_layers)

    def _find_layer_by_name(self, layers, layer_name):
        """Find a single layer by name using multiple matching strategies."""
        layer_name_lower = layer_name.lower()

        # Try exact match first
        for layer in layers:
            if layer.get('name') == layer_name:
                return layer

        # Try case-insensitive match
        for layer in layers:
            if layer.get('name', '').lower() == layer_name_lower:
                return layer

        # Try partial match (contains)
        for layer in layers:
            if layer_name_lower in layer.get('name', '').lower():
                return layer

        return None

    def _combine_layers_metadata(self, layers):
        """Combine metadata from multiple layers."""
        if not layers:
            return {}

        if len(layers) == 1:
            return self._process_layer_metadata(layers[0])

        # Combine metadata from all layers
        combined_metadata = {}

        # Combine titles
        titles = [layer.get('title') for layer in layers if layer.get('title')]
        if titles:
            combined_metadata['title'] = ' + '.join(titles)

        # Combine abstracts (with title prepending for each layer)
        abstracts = []
        for layer in layers:
            abstract = layer.get('abstract')
            title = layer.get('title')

            if abstract and title:
                abstracts.append(f"{title}: {abstract}")
            elif abstract:
                abstracts.append(abstract)
            elif title:
                abstracts.append(title)

        if abstracts:
            combined_metadata['abstract'] = ' + '.join(abstracts)

        # Combine attributions (use first one found)
        for layer in layers:
            legend = layer.get('legend')
            if legend:
                combined_metadata['attribution'] = {
                    'title': f"Layers: {', '.join([l.get('name', '') for l in layers])}",
                    'url': legend.get('url', '')
                }
                break

        return combined_metadata

    def _process_layer_metadata(self, layer):
        """Process and format layer metadata."""
        metadata = {}

        # Title
        if layer.get('title'):
            metadata['title'] = layer['title']

        # Abstract (with title prepending)
        abstract = layer.get('abstract')
        title = layer.get('title')

        if abstract and title:
            # Prepend title to abstract
            metadata['abstract'] = f"{title}: {abstract}"
        elif abstract:
            metadata['abstract'] = abstract
        elif title:
            metadata['abstract'] = title

        # Attribution
        legend = layer.get('legend')
        if legend:
            metadata['attribution'] = {
                'title': f"Layer: {layer.get('name', '')}",
                'url': legend.get('url', '')
            }

        return metadata


# Module-level singleton instance for backwards compatibility and easy access
_metadata_manager = None


def get_metadata_manager():
    """Get the singleton WMSMetadataManager instance."""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = WMSMetadataManager()
    return _metadata_manager


def merge_auto_metadata(manual_metadata, auto_metadata):
    """
    Merge auto-fetched metadata with manual configuration.
    Manual configuration takes priority over auto metadata.
    """
    if not auto_metadata:
        return manual_metadata or {}

    merged = auto_metadata.copy()

    if manual_metadata:
        # Manual metadata overrides auto metadata
        for key, value in manual_metadata.items():
            if value is not None:
                merged[key] = value

    return merged
