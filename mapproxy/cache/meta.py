from __future__ import print_function
import struct
from mapproxy.cache.base import tile_buffer
from mapproxy.image import ImageSource

class MetaTileFile(object):
    def __init__(self, meta_tile):
        self.meta_tile = meta_tile

    def write_tiles(self, tiles):
        tile_positions = []
        count = len(tiles) # self.meta_tile.grid_size[0]
        header_size = (
              4   # META
            + 4   # metasize**2
            + 3*4 # x, y, z
            + count * 8 #offset/size * tiles
        )
        with open('/tmp/foo.metatile', 'wb') as f:
            f.write("META")
            f.write(struct.pack('i', count))
            f.write(struct.pack('iii', *tiles[0].coord))
            offsets_header_pos = f.tell()
            f.seek(header_size, 0)

            for tile in tiles:
                offset = f.tell()
                with tile_buffer(tile) as buf:
                    tile_data = buf.read()
                    f.write(tile_data)
                tile_positions.append((offset, len(tile_data)))

            f.seek(offsets_header_pos, 0)
            for offset, size in tile_positions:
                f.write(struct.pack('ii', offset, size))

    def _read_header(self, f):
        f.seek(0, 0)
        assert f.read(4) == "META"
        count, x, y, z = struct.unpack('iiii', f.read(4*4))
        tile_positions = []
        for i in range(count):
            offset, size = struct.unpack('ii', f.read(4*2))
            tile_positions.append((offset, size))

        return tile_positions

    def read_tiles(self):
        with open('/tmp/foo.metatile', 'rb') as f:
            tile_positions = self._read_header(f)

            for i, (offset, size) in enumerate(tile_positions):
                f.seek(offset, 0)
                # img = ImageSource(BytesIO(f.read(size)))
                open('/tmp/img-%02d.png' % i, 'wb').write(f.read(size))

if __name__ == '__main__':
    from io import BytesIO
    from mapproxy.cache.tile import Tile
    from mapproxy.test.image import create_tmp_image

    tiles = []
    img = create_tmp_image((256, 256))
    for x in range(8):
        for y in range(8):
            tiles.append(Tile((x, y, 4), ImageSource(BytesIO(img))))

    m = MetaTileFile(None)
    print('!')
    m.write_tiles(tiles)
    print('!')
    m.read_tiles()
    print('!')

    x = y = 0
    METATILE = 8
    for meta in range(METATILE ** 2):
        print(x + (meta / METATILE), y + (meta % METATILE));