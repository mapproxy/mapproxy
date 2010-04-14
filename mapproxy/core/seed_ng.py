from mapproxy.core import grid


"""
>>> g = grid.TileGrid()
>>> seed_bbox = (-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428)
>>> seed_level = 2, 4
>>> seed(g, seed_bbox, seed_level)

"""


def seed(tile_grid, seed_bbox, seed_level):
    def _seed(tile_grid, sub_seed_bbox, level, max_level):
        if level < max_level:
            _bbox, _tiles, subtiles = tile_grid._get_affected_level_tiles(sub_seed_bbox, level)
            for subtile in subtiles:
                if subtile is None: continue
                sub_bbox = tile_grid.tile_bbox(subtile)
                if grid.bbox_intersects(sub_bbox, seed_bbox):
                    _seed(tile_grid, sub_bbox, level+1, max_level)
        _bbox, tiles, subtiles = tile_grid._get_affected_level_tiles(sub_seed_bbox, level)
        print level, tiles, sub_seed_bbox
    
    _seed(tile_grid, seed_bbox, seed_level[0], seed_level[1])


if __name__ == "__main__":
    g = grid.TileGrid(res='sqrt2')
    seed_bbox = (-20037508.3428, -20037508.3428, 20037508.3428, 20037508.3428)
    seed_level = 0, 6
    seed(g, seed_bbox, seed_level)