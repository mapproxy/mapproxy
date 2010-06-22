# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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
