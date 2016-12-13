# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
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
Tile caching (creation, caching and retrieval of tiles).

.. digraph:: Schematic Call Graph

    ranksep = 0.1;
    node [shape="box", height="0", width="0"]

    cl  [label="CacheMapLayer" href="<mapproxy.layer.CacheMapLayer>"]
    tm  [label="TileManager",  href="<mapproxy.cache.tile.TileManager>"];
    fc      [label="FileCache", href="<mapproxy.cache.file.FileCache>"];
    s       [label="Source", href="<mapproxy.source.Source>"];

    {
        cl -> tm [label="load_tile_coords"];
        tm -> fc [label="load\\nstore\\nis_cached"];
        tm -> s  [label="get_map"]
    }


"""
